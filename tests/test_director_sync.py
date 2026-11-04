import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from PIL import Image
from core import Store,now
from miniapp import MiniService,MiniServer,initialize
from test_miniapp import signed,TOKEN
import director_auth as auth
import catalog_sync as sync
import director


class DirectorSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite3'
        self.s=Store(self.path);self.s.configure([10],[20]);initialize(self.path);self.service=MiniService(self.s,TOKEN)
        with self.s.db:
            self.point=self.s.add('points',name='Warehouse');self.target=self.s.add('points',name='Showcase')
            self.s.point_kind(10,self.target,'vitrina')
            self.product=self.s.product(10,'Tire 315/80','125.00')
            self.s.db.execute('UPDATE products SET size=? WHERE id=?',('315/80',self.product))
            self.client=self.s.client(20,'Client','+998901234567','','')
            self.s.move(20,self.product,self.point,10,'in','opening')
        self.settings=dict(product=self.product,published=True,price='125.00',category='TBR',model='T',description_uz='UZ',description_ru='RU',stock_mode='exact',points=[self.point,self.target],photos=[])

    def tearDown(self):self.s.db.close();self.temp.cleanup()

    def save(self,**updates):
        with self.s.db:sync.save_settings(self.s,10,{**self.settings,**updates})

    def version(self):return self.s.db.execute('SELECT version FROM catalog_outbox WHERE product=?',(self.product,)).fetchone()[0]

    def test_migration_reopen_preserves_business_data_and_versions(self):
        before={t:self.s.rows('SELECT * FROM '+t) for t in ('products','clients','users','stock','inventory_lots','movements')};version=self.version()
        other=Store(self.path)
        for table,rows in before.items():self.assertEqual(rows,other.rows('SELECT * FROM '+table))
        self.assertEqual(version,other.db.execute('SELECT version FROM catalog_outbox').fetchone()[0]);other.db.close()

    def test_default_hidden_unknown_stock_and_unknown_price(self):
        p=sync.snapshot(self.s,self.product)
        self.assertFalse(p['published']);self.assertIsNone(p['stock']);self.assertIsNone(p['available']);self.assertIsNone(p['price_cents'])
        self.save();self.assertIsNone(sync.snapshot(self.s,self.product)['stock'])
        with self.s.db:self.s.opening_stock(10,self.product,self.target,0)
        p=sync.snapshot(self.s,self.product);self.assertEqual(p['stock'],10);self.assertEqual(p['price_cents'],12500);self.assertTrue(p['available'])
        self.save(price='');self.assertIsNone(sync.snapshot(self.s,self.product)['price_cents'])
        with self.assertRaises(ValueError):self.save(price='125.001')

    def test_approved_bot_price_mode_tracks_verified_usd_without_relabeling_uzs(self):
        self.save(price_mode='bot')
        self.assertEqual(sync.snapshot(self.s,self.product)['price_cents'],12500)
        with self.s.db:self.s.edit_product(10,self.product,'Tire','B','315/80','126.01')
        self.assertEqual(sync.snapshot(self.s,self.product)['price_cents'],12601)
        with self.s.db:self.s.db.execute("UPDATE products SET currency='UZS' WHERE id=?",(self.product,))
        self.assertIsNone(sync.snapshot(self.s,self.product)['price_cents'])

    def test_rollback_includes_outbox_and_settings(self):
        version=self.version()
        with self.assertRaises(RuntimeError):
            with self.s.db:
                self.s.move(20,self.product,self.point,2,'in','rollback')
                self.assertGreater(self.version(),version);raise RuntimeError()
        self.assertEqual(self.version(),version);self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],10)

    def test_sale_receipt_cancel_return_and_transfer_update_snapshot(self):
        self.save(points=[self.point,self.target])
        with self.s.db:self.s.opening_stock(10,self.product,self.target,0)
        version=self.version()
        with self.s.db:
            supplier=self.s.supplier_save(10,'Supplier')
            receipt=self.s.receive(10,self.product,supplier,'50',[{'point':self.point,'qty':5}])
        debt=self.s.suppliers(10)['balances'][0]['balance']
        self.assertGreater(self.version(),version)
        sale=self.service.write(20,'sale-sync-fixture-001','sell',{'client':self.client,'point':self.point,'items':[{'product':self.product,'qty':2,'price':'125'}],'paid':'10','payment':'cash'})['id']
        self.assertEqual(sync.snapshot(self.s,self.product)['stock'],13)
        self.assertEqual(self.s.suppliers(10)['balances'][0]['balance'],debt)
        self.service.write(10,'cancel-fixture-00001','cancel_sale',{'sale':sale,'reason':'cancel','settlement':True,'expected_paid':1000})
        self.assertEqual(sync.snapshot(self.s,self.product)['stock'],15)
        self.service.write(10,'transfer-fixture-001','stock_transfer',{'product':self.product,'source':self.point,'target':self.target,'qty':12,'reason':'display'})
        self.assertEqual(sync.snapshot(self.s,self.product)['stock'],15)
        self.assertEqual(sum(x['qty'] for x in self.s.rows('SELECT qty FROM inventory_lots')),15)
        lots=self.s.rows('SELECT * FROM inventory_lots WHERE receipt=? AND point=?',(receipt,self.target));self.assertEqual(lots[0]['qty'],2)
        self.service.write(10,'return-fixture-00001','supplier_return',{'lot':lots[0]['id'],'qty':1,'note':'return'})
        self.assertEqual(sync.snapshot(self.s,self.product)['stock'],14)
        self.assertEqual(self.s.suppliers(10)['balances'][0]['balance'],debt-5000)

    def test_transfer_failure_and_inventory_optimistic_concurrency(self):
        version=self.version()
        with self.assertRaises(ValueError):self.service.write(10,'transfer-failure-001','stock_transfer',{'product':self.product,'source':self.point,'target':self.target,'qty':11,'reason':'test'})
        self.assertEqual(self.version(),version)
        data={'product':self.product,'point':self.point,'actual':8,'expected':10,'reason':'count'}
        self.service.write(10,'inventory-count-001','inventory_count',data)
        self.service.write(10,'inventory-count-001','inventory_count',data)
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],8)
        with self.assertRaises(ValueError):self.service.write(10,'inventory-count-002','inventory_count',data)
        self.assertTrue(self.s.rows("SELECT * FROM audit WHERE action LIKE 'inventory_count:%'"))

    def test_retained_transfer_command_and_single_director_menu_entry(self):
        from bot import Bot
        b=Bot(self.s)
        with self.s.db:b.execute(10,'transfer',{'product':self.product,'source':self.point,'destination':self.target,'qty':2,'note':'display'})
        self.assertEqual(self.s.rows('SELECT SUM(qty) qty FROM stock')[0]['qty'],10)
        with self.assertRaises(PermissionError):b.execute(20,'transfer',{'product':self.product,'source':self.point,'destination':self.target,'qty':1,'note':'no'})
        with patch.dict('os.environ',{'PUBLIC_APP_URL':'https://cabinet.test'}):
            director_buttons=[x['text'] for row in b.keyboard(10)['keyboard'] for x in row]
            employee_buttons=[x['text'] for row in b.keyboard(20)['keyboard'] for x in row]
        self.assertEqual(director_buttons.count('📊 Direktor kabineti'),1)
        self.assertNotIn('📊 Direktor kabineti',employee_buttons)
        self.assertIn('💰 Sotuv kiritish',employee_buttons)

    def test_concurrent_changes_serialize_and_do_not_lose_stock(self):
        failures=[]
        def worker():
            s=Store(self.path)
            try:
                with s.db:s.move(20,self.product,self.point,1,'in','parallel')
            except Exception as e:failures.append(e)
            finally:s.db.close()
        threads=[threading.Thread(target=worker) for _ in range(4)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(failures,[]);self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],14)

    def test_retry_limit_and_manual_requeue(self):
        with self.s.db:self.s.db.execute('UPDATE catalog_outbox SET attempts=9,next_attempt=0')
        def fail(_):raise TimeoutError()
        sync.run_once(self.s,fail,None)
        self.assertFalse(sync.run_once(self.s,fail,None))
        self.service.write(10,'manual-retry-limit-1','website_retry',{'product':self.product})
        self.assertTrue(sync.run_once(self.s,lambda _: {'ok':True},None))
        self.assertEqual(self.s.rows('SELECT attempts FROM catalog_outbox')[0]['attempts'],0)

    def test_session_expiry_role_revocation_and_approval_expiry(self):
        token=auth.telegram(self.s,signed(10,query_id='expiry'),TOKEN)
        with self.s.db:self.s.db.execute('UPDATE director_sessions SET expires=0')
        with self.assertRaises(PermissionError):auth.identity(self.s,auth.COOKIE+'='+token)
        code=auth.start(self.s,'expired-browser','local-expiry')
        with self.s.db:self.s.db.execute('UPDATE director_logins SET expires=0')
        with self.assertRaises(ValueError):auth.approve(self.s,10,code)
        token=auth.telegram(self.s,signed(10,query_id='role-revoke'),TOKEN)
        with self.s.db:self.s.db.execute("UPDATE users SET role='employee' WHERE id=10")
        with self.assertRaises(PermissionError):auth.identity(self.s,auth.COOKIE+'='+token)

    def test_photo_delete_and_inactive_product_replicate(self):
        with self.s.db:self.s.db.execute('INSERT INTO product_photos VALUES(?,?,?)',(self.product,0,'telegram-file'))
        self.save(photos=['telegram-file'])
        version=self.version()
        with self.s.db:self.s.db.execute('DELETE FROM product_photos WHERE product=?',(self.product,));self.s.db.execute('UPDATE products SET active=0 WHERE id=?',(self.product,))
        payload=sync.snapshot(self.s,self.product);self.assertFalse(payload['published']);self.assertEqual(payload['_photos'],[]);self.assertGreater(self.version(),version)

    def test_network_failure_retry_and_newer_write_during_delivery(self):
        self.save()
        def fail(_):raise TimeoutError()
        self.assertTrue(sync.run_once(self.s,fail,None));row=self.s.rows('SELECT * FROM catalog_outbox')[0];self.assertEqual(row['attempts'],1);self.assertGreater(row['next_attempt'],int(time.time()))
        self.assertFalse(sync.run_once(self.s,fail,None))
        with self.s.db:self.s.db.execute('UPDATE catalog_outbox SET next_attempt=0')
        seen=[]
        def send(p):
            seen.append(p)
            with self.s.db:self.s.move(20,self.product,self.point,1,'in','during delivery')
            return {'ok':True}
        sync.run_once(self.s,send,None);row=self.s.rows('SELECT * FROM catalog_outbox')[0]
        self.assertGreater(row['version'],row['delivered_version']);self.assertNotIn('_photos',seen[0]);self.assertNotIn('cost',seen[0]);self.assertEqual(seen[0]['currency'],'USD')
        sync.run_once(self.s,lambda p:{'ok':True},None)
        row=self.s.rows('SELECT * FROM catalog_outbox')[0];self.assertEqual(row['version'],row['delivered_version']);self.assertTrue(row['last_success'])

    def test_image_validation_cache_and_payload_privacy(self):
        out=io.BytesIO();Image.new('RGB',(12,12),'red').save(out,format='PNG');payload=sync.image_payload(out.getvalue());self.assertEqual(payload['type'],'image')
        with self.assertRaises(ValueError):sync.image_payload(b'\xff\xd8not really an image')
        with self.s.db:self.s.db.execute('INSERT INTO product_photos VALUES(?,?,?)',(self.product,0,'private-file-id'))
        self.save(photos=['private-file-id']);calls=[]
        def send(p):
            calls.append(p)
            return {'path':'/media/'+p['sha256']+'.jpg'} if p['type']=='image' else {'ok':True}
        sync.run_once(self.s,send,lambda *_:out.getvalue())
        self.assertEqual(sum(p['type']=='image' for p in calls),1)
        with self.s.db:self.s.db.execute('UPDATE catalog_outbox SET version=version+1')
        sync.run_once(self.s,send,lambda *_:self.fail('cached image loaded again'))
        self.assertEqual(sum(p['type']=='image' for p in calls),1)
        self.assertNotIn('private-file-id',json.dumps(calls));self.assertNotIn('supplier',json.dumps(calls))

    def test_director_only_reads_and_writes(self):
        for kind in ('overview','sales','stock','clients','suppliers','managers','staff','website','audit'):
            with self.assertRaises(PermissionError):director.read(self.service,20,kind,{})
            director.read(self.service,10,kind,{})
        for cmd in ('website_save','website_retry','stock_transfer','inventory_count'):
            with self.assertRaises(PermissionError):self.service.write(20,'forbidden-command-001',cmd,self.settings)

    def test_telegram_one_use_expiry_and_revocation(self):
        token=auth.telegram(self.s,signed(10),TOKEN)
        self.assertEqual(auth.identity(self.s,auth.COOKIE+'='+token)[0]['id'],10)
        with self.assertRaises(PermissionError):auth.telegram(self.s,signed(10),TOKEN)
        with self.assertRaises(PermissionError):auth.telegram(self.s,signed(20),TOKEN)
        with self.assertRaises(Exception):auth.telegram(self.s,signed(10,age=301),TOKEN)
        with self.assertRaises(PermissionError):auth.identity(self.s,auth.COOKIE+'='+token,'bad',True)
        auth.identity(self.s,auth.COOKIE+'='+token,auth.csrf(token),True)
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=10')
        with self.assertRaises(PermissionError):auth.identity(self.s,auth.COOKIE+'='+token)
        with self.s.db:self.s.db.execute('UPDATE users SET active=1 WHERE id=10')
        with self.assertRaises(PermissionError):auth.identity(self.s,auth.COOKIE+'='+token)

    def test_desktop_approval_bound_one_use_limited_and_director_only(self):
        code=auth.start(self.s,'browser-a','127.0.0.1')
        with self.assertRaises(PermissionError):auth.approve(self.s,20,code)
        auth.approve(self.s,10,code);self.s.db.commit()
        with self.assertRaises(PermissionError):auth.poll(self.s,'browser-b')
        token=auth.poll(self.s,'browser-a');self.assertIsInstance(token,str)
        with self.assertRaises(PermissionError):auth.poll(self.s,'browser-a')
        with self.assertRaises(ValueError):auth.approve(self.s,10,code)
        for i in range(4):auth.start(self.s,str(i),'127.0.0.1')
        with self.assertRaises(PermissionError):auth.start(self.s,'over-limit','127.0.0.1')

    def test_historical_period_received_current_debt_and_currency(self):
        sale=self.service.write(20,'period-sale-0000001','sell',{'client':self.client,'point':self.point,'items':[{'product':self.product,'qty':1,'price':'125'}],'paid':'25','payment':'cash'})['id']
        with self.s.db:
            self.s.db.execute("UPDATE sales SET created='2026-01-31T23:59:59+05:00' WHERE id=?",(sale,))
            self.s.db.execute("UPDATE payments SET created='2026-02-01T00:00:00+05:00' WHERE sale=?",(sale,))
        a=director.read(self.service,10,'overview',{'start':'2026-01-31','end':'2026-01-31'})
        b=director.read(self.service,10,'overview',{'start':'2026-02-01','end':'2026-02-01'})
        self.assertEqual((a['total'],a['received'],b['total'],b['received']),(12500,0,0,2500));self.assertEqual(a['debt'],10000)
        self.assertIsNone(a['profit']);self.assertIsNone(a['cash_balance'])
        with self.assertRaises(ValueError):director.read(self.service,10,'overview',{'start':'2026-02-01','end':'2026-01-31'})

    def test_legacy_uzs_review_does_not_relabel(self):
        with self.s.db:self.s.db.execute("UPDATE products SET currency='UZS',price=1250000 WHERE id=?",(self.product,))
        data=sync.inventory(self.s.db);self.assertEqual(len(data['legacy_price_review']),1);self.assertEqual(data['products'][0]['currency'],'UZS');self.assertIsNone(sync.snapshot(self.s,self.product)['price_cents'])

    def test_http_browser_auth_logout_origin_and_employee_rejection(self):
        server=MiniServer(('127.0.0.1',0),self.path,TOKEN,'https://cabinet.test');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1])
        def request(path,body=None,cookie='',csrf='',origin='https://cabinet.test'):
            req=Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':origin,'Cookie':cookie,'X-CSRF-Token':csrf})
            try:
                with urlopen(req) as r:return r.status,r.headers,json.loads(r.read())
            except HTTPError as e:return e.code,e.headers,json.loads(e.read())
        try:
            self.assertEqual(request('/director-api/overview')[0],403)
            self.assertEqual(request('/director-auth/telegram',{'initData':signed(20)})[0],403)
            self.assertEqual(request('/director-auth/start',{},origin='https://evil.test')[0],403)
            code,headers,data=request('/director-auth/start',{});self.assertEqual(code,200);browser=headers['Set-Cookie'].split(';')[0]
            auth.approve(self.s,10,data['command'].split()[1]);self.s.db.commit()
            self.assertEqual(request('/director-auth/poll',{},auth.PRECOOKIE+'=other')[0],403)
            code,headers,data=request('/director-auth/poll',{},browser);self.assertEqual(code,200);self.assertTrue(data['approved']);cookie=headers.get_all('Set-Cookie')[0].split(';')[0]
            self.assertIn('HttpOnly',headers.get_all('Set-Cookie')[0]);self.assertIn('Secure',headers.get_all('Set-Cookie')[0]);self.assertIn('SameSite=Strict',headers.get_all('Set-Cookie')[0])
            code,_,me=request('/director-auth/me',cookie=cookie);self.assertEqual(code,200)
            self.assertEqual(request('/director-api/overview',cookie=cookie)[0],200)
            with urlopen(Request(base+'/director-api/report',headers={'Cookie':cookie})) as report:
                self.assertEqual(report.status,200);self.assertTrue(report.read().startswith(b'PK'))
            self.assertEqual(request('/director-auth/logout',{},cookie)[0],403)
            self.assertEqual(request('/director-auth/logout',{},cookie,me['csrf'])[0],200)
            self.assertEqual(request('/director-api/overview',cookie=cookie)[0],403)
        finally:server.shutdown();server.server_close();thread.join()
