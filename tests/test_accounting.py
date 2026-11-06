import base64
import io
import json
from pathlib import Path
from queue import Queue
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core import Store, SCHEMA, now, parse_item_lines
from miniapp import MiniService, MiniServer, initialize
from openpyxl import load_workbook
from test_miniapp import TOKEN, signed


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'test.sqlite3'
        self.s = Store(self.path)
        self.s.configure([10], [20, 21])
        initialize(self.path)
        self.api = MiniService(self.s, TOKEN)
        with self.s.db:
            self.sklad = self.s.add('points', name='Sklad')
            self.vitrina = self.s.add('points', name='Vitrina', kind='vitrina')
            self.product = self.s.product(10, 'Tyre', '20')
            self.client = self.s.client(20, 'Customer', '+998901234567', '', '')
            self.supplier = self.s.supplier_save(10, 'Factory', '+998901234567', 'Initial')
        self.today = now()[:10]

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()

    def receive(self, sklad=5, vitrina=3, cost='10.25', supplier=None, currency='USD'):
        allocations = [{'point':p, 'qty':q} for p,q in ((self.sklad,sklad),(self.vitrina,vitrina)) if q]
        with self.s.db:
            return self.s.receive(20, self.product, supplier or self.supplier, cost, allocations, 'Invoice', self.today, currency)

    def qty(self, point):
        rows = self.s.rows('SELECT qty FROM stock WHERE product=? AND point=?', (self.product,point))
        return rows[0]['qty'] if rows else 0

    def balance(self, currency='USD'):
        rows = [r for r in self.s.suppliers(10)['balances'] if r['supplier']==self.supplier and r['currency']==currency]
        return rows[0]['balance'] if rows else 0

    def sell(self, lines):
        with self.s.db:
            return self.s.order(20, self.client, [dict(product=self.product,qty=q,price='20',point=p) for p,q in lines], point=self.sklad, payment='naqd')

    def report(self, supplier=None, start=None, end=None):
        return self.s.supplier_report(10, start or self.today, end or self.today, supplier)

    def assert_provenance(self):
        actual = self.s.rows('SELECT product,point,qty FROM stock ORDER BY product,point')
        lots = self.s.rows('SELECT product,point,SUM(qty) qty FROM inventory_lots GROUP BY product,point ORDER BY product,point')
        self.assertEqual(actual, lots)
        self.assertEqual(self.s.rows('PRAGMA foreign_key_check'), [])

    def test_split_receipt_updates_exact_money_stock_and_audit(self):
        ref = self.receive()
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(5,3))
        self.assertEqual(self.balance(),8200)
        self.assertEqual(self.report()['stock'][0]['qty'],3)
        self.assertEqual(self.report()['stock'][0]['supplier'],self.supplier)
        self.assertEqual(self.s.rows('SELECT action,ref FROM audit ORDER BY id DESC LIMIT 1'),[{'action':'supplier_income','ref':ref}])
        self.assert_provenance()

    def test_supplier_payment_and_return_use_original_cost(self):
        self.receive()
        lot = self.report()['lots'][0]
        with self.s.db:
            self.s.supplier_pay(10,self.supplier,'20','Bank',self.today)
            self.s.edit_product(10,self.product,'Tyre','','','999')
            self.s.supplier_return(10,lot['id'],2,'Return',self.today)
        self.assertEqual(self.balance(),4150)
        self.assertEqual(self.qty(lot['point']),3)
        self.assertEqual([r['amount'] for r in self.report()['entries']],[8200,2000,2050])
        self.assert_provenance()

    def test_multiple_suppliers_and_unassigned_stock_are_distinct(self):
        with self.s.db:
            self.s.move(20,self.product,self.vitrina,2,'in','Legacy-style receipt')
            other = self.s.supplier_save(10,'Other')
        self.receive(0,3)
        self.receive(0,4,cost='15',supplier=other)
        self.sell([(self.vitrina,6)])
        sold = {r['supplier']:r['qty'] for r in self.report()['sold']}
        self.assertEqual(sold,{None:2,self.supplier:3,other:1})
        self.assertEqual(self.report()['stock'][0]['supplier'],other)
        self.assertEqual(self.report(self.supplier)['stock'],[])
        self.assertEqual(self.report(self.supplier)['sold'][0]['qty'],3)
        self.assert_provenance()

    def test_each_sale_line_consumes_only_selected_place_and_cancels_exact_lots(self):
        self.receive(5,4)
        sale = self.sell([(self.sklad,2),(self.vitrina,3)])
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(3,1))
        self.assertEqual(self.report()['sold'][0]['qty'],3)
        with self.s.db:
            self.s.cancel_sale(10,sale,'Mistake')
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(5,4))
        self.assertEqual(self.report()['sold'],[])
        self.assertEqual(self.balance(),9225)
        with self.assertRaisesRegex(ValueError,'sale_cancelled'):
            with self.s.db:self.s.cancel_sale(10,sale,'Again')
        self.assert_provenance()

    def test_failed_second_sale_line_rolls_back_even_when_error_caught_inside_transaction(self):
        self.receive(5,1)
        before = self.s.rows('SELECT * FROM inventory_lots')
        with self.s.db:
            with self.assertRaisesRegex(ValueError,'stock'):
                self.s.order(20,self.client,[dict(product=self.product,qty=2,price='20',point=self.sklad),dict(product=self.product,qty=2,price='20',point=self.vitrina)],point=self.sklad,payment='naqd')
        self.assertEqual(self.s.rows('SELECT * FROM sales'),[])
        self.assertEqual(self.s.rows('SELECT * FROM inventory_lots'),before)
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(5,1))

    def test_reports_use_sale_location_snapshot_and_period(self):
        self.receive(2,3)
        sale = self.sell([(self.vitrina,1)])
        with self.s.db:self.s.point_kind(10,self.vitrina,'sklad')
        self.assertEqual(self.report()['stock'],[])
        self.assertEqual(self.report()['sold'][0]['qty'],1)
        with self.s.db:self.s.db.execute("UPDATE sales SET created='2020-01-01T10:00:00+05:00' WHERE id=?",(sale,))
        self.assertEqual(self.report()['sold'],[])
        self.assertEqual(self.report(start='2020-01-01',end='2020-01-01')['sold'][0]['qty'],1)

    def test_writeoff_and_legacy_returns_keep_lots_consistent(self):
        self.receive()
        with self.s.db:
            self.s.move(10,self.product,self.sklad,2,'writeoff','Damaged')
            self.s.move(20,self.product,self.vitrina,1,'return','Unknown supplier')
        self.assert_provenance()
        self.assertEqual(self.balance(),8200)
        self.assertTrue(any(r['supplier'] is None for r in self.report()['stock']))

    def test_manager_formula_currency_scope_and_supplier_payment_once(self):
        self.receive()
        self.api.write(10,'manager-fund-00001','manager_record',dict(manager=20,kind='fund',amount='100',note='Cash',date=self.today))
        self.api.write(20,'manager-exp-000001','manager_record',dict(kind='expense',amount='5',note='Taxi'))
        data=dict(supplier=self.supplier,manager=20,amount='20',note='Supplier payment')
        first=self.api.write(20,'manager-supplier-01','supplier_payment',data)
        self.assertEqual(first,self.api.write(20,'manager-supplier-01','supplier_payment',data))
        self.api.write(20,'manager-return-001','manager_record',dict(kind='return',amount='10',note='Returned'))
        with self.s.db:
            self.s.manager_record(10,21,'fund','50')
            self.s.manager_record(10,20,'fund','1000',currency='UZS')
        pending=self.s.manager_account(20)
        self.assertEqual(next(r for r in pending['balances'] if r['currency']=='USD')['pending_return'],1000)
        self.assertEqual(next(r for r in pending['balances'] if r['currency']=='USD')['balance'],7500)
        ref=next(r['id'] for r in pending['entries'] if r['kind']=='return')
        self.api.write(10,'accept-manager-ret-1','manager_accept_return',dict(entry=ref))
        balances=self.s.manager_account(20)['balances']
        usd=next(r for r in balances if r['currency']=='USD')
        self.assertEqual((usd['given'],usd['expenses'],usd['returned'],usd['balance']),(10000,2500,1000,6500))
        self.assertEqual(self.balance(),6200)
        self.assertEqual({r['manager'] for r in self.s.manager_account(20)['entries']},{20})
        self.assertEqual(len(self.s.manager_account(10)['balances']),3)
        for row in self.s.manager_account(20)['entries']:
            self.assertTrue(row['date'] and row['actor'] and 'note' in row)

    def test_negative_manager_balance_is_visible_without_clamping(self):
        with self.s.db:self.s.manager_record(20,20,'expense','5')
        self.assertEqual(self.s.manager_account(20)['balances'][0]['balance'],-500)

    def test_supplier_permissions_and_manager_isolation(self):
        operations=[lambda:self.s.supplier_save(20,'No'),lambda:self.s.supplier_save(20,'No',supplier=self.supplier),lambda:self.s.suppliers(20),lambda:self.s.supplier_report(20,self.today,self.today),lambda:self.s.manager_record(20,20,'fund','10'),lambda:self.s.manager_record(20,21,'expense','10'),lambda:self.s.manager_account(20,21),lambda:self.s.supplier_pay(20,self.supplier,'1'),lambda:self.s.supplier_pay(20,self.supplier,'1',manager=21),lambda:self.s.point_kind(20,self.sklad,'vitrina')]
        for operation in operations:
            with self.subTest(operation=operation):
                with self.s.db:
                    with self.assertRaises(PermissionError):operation()
        self.assertEqual(self.s.suppliers(20,True),[{'id':self.supplier,'name':'Factory'}])
        self.assertEqual(self.s.rows('SELECT * FROM manager_entries'),[])

    def test_disabled_users_cannot_read_or_write_accounts(self):
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
        for operation in (lambda:self.s.manager_account(20),lambda:self.s.suppliers(20,True),lambda:self.s.manager_record(20,20,'expense','1'),lambda:self.s.receive(20,self.product,self.supplier,'1',[dict(point=self.sklad,qty=1)])):
            with self.assertRaises(PermissionError):
                with self.s.db:operation()

    def test_invalid_receipts_and_dates_have_no_partial_effects(self):
        invalid=[dict(allocations=[dict(point=self.sklad,qty=1),dict(point=999,qty=1)]),dict(allocations=[dict(point=self.sklad,qty=1),dict(point=self.sklad,qty=1)]),dict(allocations=[dict(point=self.sklad,qty=1.5)]),dict(allocations=[dict(point=self.sklad,qty=True)]),dict(cost='-1'),dict(cost='NaN'),dict(cost='1000000000000',allocations=[dict(point=self.sklad,qty=1000000)]),dict(currency='EUR'),dict(date='2026-02-30')]
        base=dict(product=self.product,supplier=self.supplier,cost='10',allocations=[dict(point=self.sklad,qty=2)])
        for changes in invalid:
            with self.s.db:
                with self.assertRaises(ValueError):self.s.receive(20,**{**base,**changes})
        self.assertEqual(self.s.rows('SELECT * FROM receipts'),[])
        self.assertEqual(self.s.rows('SELECT * FROM supplier_entries'),[])
        self.assertEqual(self.s.rows('SELECT * FROM inventory_lots'),[])

    def test_return_oversell_unknown_lot_and_permission_rollback(self):
        self.receive(1,0)
        lot=self.report()['lots'][0]['id']
        with self.s.db:
            for target,qty in ((lot,2),(999,1)):
                with self.assertRaises(ValueError):self.s.supplier_return(10,target,qty)
            with self.assertRaises(PermissionError):self.s.supplier_return(20,lot,1)
        self.assertEqual(self.balance(),1025)
        self.assertEqual(self.qty(self.sklad),1)
        self.assert_provenance()

    def test_supplier_edit_audits_before_after_and_preserves_identity(self):
        self.receive()
        with self.s.db:self.s.supplier_save(10,'New name','123','Edited',self.supplier)
        self.assertEqual(self.s.supplier_row(self.supplier)['name'],'New name')
        self.assertEqual(self.balance(),8200)
        audit=self.s.rows("SELECT * FROM audit WHERE action LIKE 'supplier_edit:%'")[0]
        change=json.loads(audit['action'].split(':',1)[1])
        self.assertEqual(change['before']['name'],'Factory')
        self.assertEqual(change['after']['name'],'New name')

    def test_api_receipt_and_payment_idempotency_and_request_changed(self):
        data=dict(product=self.product,supplier=self.supplier,cost='10',allocations=[dict(point=self.vitrina,qty=3)])
        first=self.api.write(20,'receipt-request-001','supplier_income',data)
        self.assertEqual(first,self.api.write(20,'receipt-request-001','supplier_income',data))
        with self.assertRaisesRegex(ValueError,'request_changed'):
            self.api.write(20,'receipt-request-001','supplier_income',{**data,'cost':'20'})
        self.assertEqual(self.balance(),3000)
        self.assertEqual(len(self.s.rows('SELECT * FROM receipts')),1)
        self.assert_provenance()

    def test_api_line_points_are_not_lost(self):
        self.receive(2,3)
        data=dict(client=self.client,point=self.sklad,items=[dict(product=self.product,qty=1,price='20',point=self.vitrina)],payment='naqd')
        self.api.write(20,'sale-with-point-001','sell',data)
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(2,2))
        history=self.api.history(20,'sales')[0]['items'][0]
        self.assertEqual(history['point_name'],'Vitrina')
        self.assertEqual(self.s.report(10,self.today,self.today)['sale_items'][0]['point'],self.vitrina)

    def test_bot_forms_receipt_sale_points_and_excel_reports(self):
        bot=self.api.b
        def send(uid,text):
            update=100+len(self.s.rows('SELECT * FROM updates'))
            bot.process(dict(update_id=update,message={'from':{'id':uid},'chat':{'type':'private','id':uid},'text':text}))
        for value in ['/prixod',str(self.product),str(self.supplier),'10.25',f'{self.sklad}|5\n{self.vitrina}|3','USD',self.today,'Invoice','Tasdiqlash']:send(20,value)
        self.assertEqual(self.balance(),8200)
        parsed=parse_item_lines(f'{self.product}|2|20|{self.vitrina}')
        self.assertEqual(parsed[0]['point'],self.vitrina)
        with self.s.db:bot.execute(20,'sell',dict(client=self.client,point=self.sklad,items=parsed,paid='0',payment='naqd'))
        self.assertEqual((self.qty(self.sklad),self.qty(self.vitrina)),(5,1))
        for value in ['/supplier_report','0',self.today,self.today,'Tasdiqlash']:send(10,value)
        documents=[json.loads(r['payload']) for r in self.s.rows('SELECT payload FROM outbox') if 'document' in json.loads(r['payload'])]
        wb=load_workbook(io.BytesIO(base64.b64decode(documents[-1]['document'])))
        self.assertIn('Yetkazib beruvchi vitrina',wb.sheetnames)

    def test_reopening_does_not_duplicate_receipts_lots_or_balances(self):
        self.receive()
        before=self.s.rows('SELECT * FROM inventory_lots')
        self.s.db.close()
        self.s=Store(self.path)
        self.assertEqual(self.s.rows('SELECT * FROM inventory_lots'),before)
        self.assertEqual(self.balance(),8200)
        self.assert_provenance()

    def test_legacy_excel_import_and_supplier_receipts_keep_distinct_lots(self):
        from openpyxl import Workbook
        from excel_import import InventoryExcel
        self.receive(0,2)
        wb=Workbook();ws=wb.active
        ws.append(['ID','Nomi','Narx USD','Kelgan dona'])
        ws.append([self.product,'Tyre','22',3])
        stream=io.BytesIO();wb.save(stream)
        encoded=base64.b64encode(stream.getvalue()).decode()
        importer=InventoryExcel(self.s)
        preview=importer.preview(10,encoded,self.vitrina)
        with self.s.db:importer.apply(10,encoded,self.vitrina,'',preview['fingerprint'])
        self.assertEqual(self.qty(self.vitrina),5)
        self.assertEqual(self.balance(),2050)
        self.sell([(self.vitrina,4)])
        self.assertEqual({r['supplier']:r['qty'] for r in self.report()['sold']},{None:3,self.supplier:1})
        self.assert_provenance()

    def test_linked_manager_expense_rolls_back_if_supplier_payment_fails(self):
        self.receive()
        with self.s.db:self.s.manager_record(10,20,'fund','100')
        original=self.s.log
        def log(uid,action,ref=None):
            if action=='supplier_payment':raise ValueError('injected failure')
            return original(uid,action,ref)
        with self.s.db:
            with patch.object(self.s,'log',side_effect=log):
                with self.assertRaisesRegex(ValueError,'injected failure'):
                    self.s.supplier_pay(20,self.supplier,'20',manager=20)
        self.assertEqual(len(self.s.manager_account(20)['entries']),1)
        self.assertEqual(self.s.manager_account(20)['balances'][0]['balance'],10000)
        self.assertEqual(self.balance(),8200)
        self.assertEqual(self.s.rows("SELECT * FROM audit WHERE action='manager_expense'"),[])

    def concurrent(self,cmd,data,keys):
        barrier=threading.Barrier(2);results=Queue()
        def run(key):
            store=None
            try:
                store=Store(self.path);api=MiniService(store,TOKEN)
                barrier.wait(timeout=5)
                results.put(api.write(20,key,cmd,data))
            except Exception as error:results.put(error)
            finally:
                if store:store.db.close()
        threads=[threading.Thread(target=run,args=(key,),daemon=True) for key in keys]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        return [results.get(timeout=1) for _ in threads]

    def test_concurrent_sales_cannot_sell_same_stock_twice(self):
        self.receive(0,1)
        data=dict(client=self.client,point=self.vitrina,items=[dict(product=self.product,qty=1,price='20',point=self.vitrina)],payment='naqd')
        results=self.concurrent('sell',data,['concurrent-sale-0001','concurrent-sale-0002'])
        self.assertEqual(sum(isinstance(r,dict) for r in results),1,results)
        self.assertEqual(sum(isinstance(r,ValueError) and str(r)=='stock' for r in results),1,results)
        self.assertEqual(self.qty(self.vitrina),0)
        self.assertEqual(len(self.s.rows('SELECT * FROM sales')),1)
        self.assert_provenance()

    def test_concurrent_receipt_retries_create_one_debt(self):
        data=dict(product=self.product,supplier=self.supplier,cost='10.25',allocations=[dict(point=self.vitrina,qty=2)])
        results=self.concurrent('supplier_income',data,['concurrent-receipt-1']*2)
        self.assertEqual(results[0],results[1])
        self.assertIsInstance(results[0],dict)
        self.assertEqual(self.balance(),2050)
        self.assertEqual(self.qty(self.vitrina),2)
        self.assert_provenance()

    def test_migration_failure_rolls_back_ddl_without_touching_legacy_tables(self):
        from accounting import migrate,TABLES
        from types import SimpleNamespace
        db=sqlite3.connect(':memory:')
        try:
            db.executescript(SCHEMA)
            with patch('accounting.TABLES',(*TABLES,'SELECT missing_column FROM meta')):
                with self.assertRaises(sqlite3.OperationalError):migrate(SimpleNamespace(db=db))
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name IN ('suppliers','receipts','inventory_lots','manager_entries')").fetchall(),[])
            self.assertEqual(db.execute("SELECT * FROM meta WHERE key='accounting_v1'").fetchall(),[])
            self.assertTrue(db.execute("SELECT 1 FROM sqlite_master WHERE name='products'").fetchone())
        finally:db.close()

    def test_legacy_database_migrates_without_inventing_supplier_attribution(self):
        path=Path(self.temp.name)/'old.sqlite3'
        db=sqlite3.connect(path)
        db.executescript(SCHEMA)
        db.execute("INSERT INTO users(id,role,name) VALUES(10,'director','Old director')")
        db.execute("INSERT INTO points(id,name) VALUES(1,'Old place')")
        db.execute("INSERT INTO products(id,name,price,photo) VALUES(1,'Old tyre',12345,'old-photo')")
        db.execute('INSERT INTO stock VALUES(1,1,7)')
        db.execute("INSERT INTO clients VALUES(1,'Old customer','123','','',10,'2020-01-01')")
        db.execute("INSERT INTO sales VALUES(1,1,1,10,100,0,'naqd','2020-01-01T12:00:00+05:00')")
        db.execute("INSERT INTO sale_items VALUES(1,1,1,'Old tyre',1,100,0)")
        db.commit();db.close()
        old=Store(path)
        try:
            self.assertEqual(old.one('products',1)['price'],12345)
            self.assertEqual(old.one('products',1)['photo'],'old-photo')
            self.assertEqual(old.rows('SELECT qty FROM stock'),[{'qty':7}])
            self.assertEqual(old.suppliers(10)['suppliers'],[])
            self.assertIsNone(old.rows('SELECT receipt FROM inventory_lots')[0]['receipt'])
            self.assertIsNone(old.rows('SELECT point FROM sale_items')[0]['point'])
            with old.db:old.point_kind(10,1,'vitrina')
            report=old.supplier_report(10,'2020-01-01','2020-01-01')
            self.assertEqual(report['stock'][0]['qty'],7)
            self.assertIsNone(report['stock'][0]['supplier'])
            self.assertIsNone(report['sold'][0]['supplier'])
            with old.db:old.cancel_sale(10,1,'Old sale cancellation')
            self.assertEqual(old.rows('SELECT qty FROM stock')[0]['qty'],8)
            self.assertEqual(old.rows('PRAGMA foreign_key_check'),[])
        finally:old.db.close()

    def test_http_accounting_reads_are_authenticated_and_scoped(self):
        self.receive()
        with self.s.db:self.s.manager_record(10,21,'fund','12')
        server=MiniServer(('127.0.0.1',0),self.path,TOKEN)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            origin='http://127.0.0.1:'+str(server.server_port)
            def get(path,uid):
                return json.load(urlopen(Request(origin+path,headers={'X-Telegram-Init-Data':signed(uid)}),timeout=5))
            for path in ('/api/suppliers','/api/supplier-report'):
                with self.assertRaises(HTTPError) as error:get(path,20)
                self.assertEqual(error.exception.code,403)
            self.assertEqual(get('/api/suppliers?picker=1',20),[{'id':self.supplier,'name':'Factory'}])
            self.assertEqual(get('/api/manager-account',20)['entries'],[])
            self.assertEqual(get('/api/manager-account',10)['balances'][0]['balance'],1200)
            with self.assertRaises(HTTPError):get('/api/manager-account?manager=21',20)
            self.assertEqual(get('/api/supplier-report',10)['stock'][0]['qty'],3)
            data=dict(cmd='supplier_income',data=dict(product=self.product,supplier=self.supplier,cost='1',allocations=[dict(point=self.vitrina,qty=1)]))
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(origin+'/api/action',data=json.dumps(data).encode(),headers={'X-Telegram-Init-Data':signed(20),'Content-Type':'application/json','Idempotency-Key':'http-account-test-01'}),timeout=5)
            self.assertEqual(error.exception.code,400)
        finally:
            server.shutdown();server.server_close();thread.join(3)
