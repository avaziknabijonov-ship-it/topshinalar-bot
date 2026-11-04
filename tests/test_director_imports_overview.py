import base64
import io
import json
import random
import string
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from openpyxl import Workbook,load_workbook
from core import Store,now
from miniapp import MiniService,MiniServer,initialize
import director_auth as auth
import director


def encoded_xlsx(rows):
    wb=Workbook();ws=wb.active;ws.append(['Nomi','Narx USD','Kelgan dona'])
    for row in rows:ws.append(row)
    stream=io.BytesIO();wb.save(stream);return base64.b64encode(stream.getvalue()).decode()


class DirectorImportOverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.sqlite3';self.s=Store(self.path);self.s.configure([10],[20]);initialize(self.path);self.service=MiniService(self.s,'fixture-token')
        with self.s.db:
            self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Original tire','125');self.s.move(20,self.product,self.point,10,'in','fixture');self.client=self.s.client(20,'Client','+998900000000','','')
        self.server=MiniServer(('127.0.0.1',0),self.path,'fixture-token','https://cabinet.test');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_address[1])
        with self.s.db:self.token=auth.issue(self.s,10)
        self.seq=0

    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.s.db.close();self.tmp.cleanup()

    def call(self,path,body=None,key=None,authorized=True,csrf=True):
        self.seq+=1;headers={'Origin':'https://cabinet.test','Content-Type':'application/json','Idempotency-Key':key or f'new-director-test-{self.seq:04}'}
        if authorized:headers['Cookie']=auth.COOKIE+'='+self.token
        if csrf:headers['X-CSRF-Token']=auth.csrf(self.token)
        try:
            with urlopen(Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=30) as r:
                raw=r.read();return r.status,json.loads(raw) if 'json' in r.headers.get('Content-Type','') else raw
        except HTTPError as e:return e.code,json.loads(e.read())

    def action(self,cmd,data,**kw):return self.call('/director-api/action',{'cmd':cmd,'data':data},**kw)

    def test_large_xlsx_uses_existing_preview_then_atomic_once_import(self):
        rng=random.Random(1);rows=[['New '+str(i)+' '+''.join(rng.choices(string.ascii_letters,k=170)),'10.01',1] for i in range(500)];data={'point':self.point,'file':encoded_xlsx(rows),'mode':'income'}
        self.assertGreater(len(json.dumps(data)),64000)
        status,preview=self.action('excel_preview',data);self.assertEqual(status,200);self.assertEqual(preview['id']['count'],500)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),1)
        payload={**data,'sheet':preview['id']['sheet'],'fingerprint':preview['id']['fingerprint']}
        status,result=self.action('excel_import',payload,key='large-import-apply-01');self.assertEqual(status,200);self.assertEqual(result['id']['count'],500)
        self.assertEqual(self.action('excel_import',payload,key='large-import-apply-01')[1],result)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),501)
        self.assertEqual(self.s.db.execute('SELECT SUM(qty) FROM stock').fetchone()[0],510)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM products WHERE price=1001 AND currency=?',('USD',)).fetchone()[0],500)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM website_products WHERE published=1').fetchone()[0],0)

    def test_document_rows_preview_confirm_and_stale_fingerprint(self):
        data={'point':self.point,'rows':[{'id':self.product,'name':'Original tire','qty':'2','price':'130.50'}]}
        status,preview=self.action('document_preview',data);self.assertEqual(status,200);self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],10)
        apply={**data,'fingerprint':preview['id']['fingerprint']}
        self.assertEqual(self.action('document_import',apply)[0],400)
        with self.s.db:self.s.move(20,self.product,self.point,1,'in','changed after preview')
        status,error=self.action('document_import',{**apply,'confirmed':True});self.assertEqual(status,400);self.assertIn('Qoldiq',error['error'])
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],11)
        preview=self.action('document_preview',data)[1]
        self.assertEqual(self.action('document_import',{**data,'fingerprint':preview['id']['fingerprint'],'confirmed':True})[0],200)
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],13)

    def test_import_auth_csrf_limits_and_useful_validation_errors(self):
        data={'point':self.point,'file':encoded_xlsx([['New tire','12.34',2]]),'mode':'income'}
        self.assertEqual(self.action('excel_preview',data,authorized=False)[0],403)
        self.assertEqual(self.action('excel_preview',data,csrf=False)[0],403)
        status,error=self.action('excel_preview',{**data,'file':'invalid'});self.assertEqual(status,400);self.assertIn('Excel',error['error'])
        self.assertEqual(self.action('website_retry',{'product':self.product,'padding':'x'*70000})[0],400)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),1)
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=10')
        self.assertEqual(self.action('excel_preview',data)[0],403)

    def test_template_is_empty_real_workbook_and_private(self):
        self.assertEqual(self.call('/director-api/import-template',authorized=False)[0],403)
        status,data=self.call('/director-api/import-template');self.assertEqual(status,200)
        wb=load_workbook(io.BytesIO(data));self.assertEqual(wb.active.max_row,1);self.assertIn('Narx USD',[c.value for c in wb.active[1]])

    def test_pdf_extract_reads_actual_pdf_without_business_writes(self):
        from reportlab.pdfgen.canvas import Canvas
        stream=io.BytesIO();canvas=Canvas(stream);canvas.drawString(40,780,'Nomi | Kelgan dona | Narx USD');canvas.drawString(40,755,'PDF tire | 2 | 50.00');canvas.save()
        status,result=self.action('document_extract',{'point':self.point,'file':base64.b64encode(stream.getvalue()).decode()});self.assertEqual(status,200)
        self.assertEqual(result['id']['rows'][0]['name'],'PDF tire');self.assertEqual(result['id']['rows'][0]['qty'],'2')
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),1)

    def test_pdf_uzs_prices_require_manual_usd_input(self):
        from reportlab.pdfgen.canvas import Canvas
        stream=io.BytesIO();canvas=Canvas(stream);canvas.drawString(40,780,'Nomi | Kelgan dona | Narx UZS');canvas.drawString(40,755,'UZS tire | 2 | 500000');canvas.save()
        status,result=self.action('document_extract',{'point':self.point,'file':base64.b64encode(stream.getvalue()).decode()})
        self.assertEqual(status,200);self.assertTrue(result['id']['currency_review_required']);self.assertEqual(result['id']['rows'][0]['price'],'');self.assertEqual(result['id']['rows'][0]['source_price'],'500000')
        self.assertEqual(self.action('document_preview',{'point':self.point,'rows':result['id']['rows']})[0],400)

    def test_explicit_uzs_excel_currency_is_rejected_without_conversion(self):
        wb=Workbook();ws=wb.active;ws.append(['Nomi','Narx','Kelgan dona','Valyuta']);ws.append(['UZS Excel tire','500000',1,'UZS']);out=io.BytesIO();wb.save(out)
        status,error=self.action('excel_preview',{'point':self.point,'mode':'income','file':base64.b64encode(out.getvalue()).decode()})
        self.assertEqual(status,400);self.assertIn('USD',error['error']);self.assertEqual(len(self.s.rows('SELECT * FROM products')),1)

    def test_preview_keeps_original_price_currency_and_does_not_relabel_uzs(self):
        with self.s.db:self.s.db.execute("UPDATE products SET currency='UZS',price=1000000,price_pending=0 WHERE id=?",(self.product,))
        data={'point':self.point,'file':encoded_xlsx([['Original tire','125.00',2]]),'mode':'income'}
        status,p=self.action('excel_preview',data);self.assertEqual(status,200);self.assertEqual(p['id']['rows'][0]['old_currency'],'UZS');self.assertEqual(p['id']['rows'][0]['old_price'],1000000)
        self.assertEqual(self.s.one('products',self.product)['currency'],'UZS')

    def test_overview_period_current_balances_trend_and_review_are_separate(self):
        with self.s.db:
            sale=self.s.order(20,self.client,[{'product':self.product,'qty':1,'price':'100'}],point=self.point,paid='30',payment='card')
            self.s.db.execute("UPDATE sales SET created='2026-01-01T10:00:00+05:00' WHERE id=?",(sale,));self.s.db.execute("UPDATE payments SET created='2026-01-02T10:00:00+05:00' WHERE sale=?",(sale,))
        a=director.read(self.service,10,'overview',{'start':'2026-01-01','end':'2026-01-01'});b=director.read(self.service,10,'overview',{'start':'2026-01-02','end':'2026-01-02'})
        self.assertEqual((a['total'],a['received'],b['total'],b['received']),(10000,0,0,3000));self.assertEqual(a['debt'],7000)
        self.assertEqual(a['manager_totals'],[{'currency':'USD','debt':3000,'credit':0}]);self.assertEqual(sum(x['received'] for x in b['trend']),3000)
        self.assertEqual(a['open_money_days'],1);self.assertIsNone(a['cash_balance']);self.assertIsNone(a['profit']);self.assertTrue(a['as_of'])
        self.assertEqual(director.read(self.service,10,'sales',{'start':'2026-01-01','end':'2026-01-01','id':str(sale)})['items'][0]['id'],sale)

    def test_overview_currency_totals_no_netting_and_chart_bounded(self):
        with self.s.db:
            self.s.manager_record(10,20,'fund','10');self.s.manager_record(10,20,'expense','50',currency='UZS')
            supplier=self.s.supplier_save(10,'Supplier');self.s.receive(10,self.product,supplier,'10',[{'point':self.point,'qty':1}],currency='USD');self.s.receive(10,self.product,supplier,'1000',[{'point':self.point,'qty':1}],currency='UZS')
        data=director.read(self.service,10,'overview',{'start':'2020-01-01','end':'2030-01-01'})
        self.assertEqual(data['manager_totals'],[{'currency':'USD','debt':1000,'credit':0},{'currency':'UZS','debt':0,'credit':5000}]);self.assertLessEqual(len(data['trend']),45)
        self.assertEqual({r['currency']:r['debt'] for r in data['supplier_totals']},{'USD':1000,'UZS':100000})

    def test_lowstock_only_known_inventory_and_authorized(self):
        with self.s.db:
            self.s.set_minimum(10,self.product,self.point,12);point=self.s.add('points',name='Uncounted');self.s.set_minimum(10,self.product,point,12)
        overview=director.read(self.service,10,'overview',{});rows=director.read(self.service,10,'lowstock',{})
        self.assertEqual(len(overview['lowstock']),1);self.assertEqual(rows['total'],1);self.assertEqual(rows['items'][0]['qty'],10)
        with self.assertRaises(PermissionError):director.read(self.service,20,'overview',{})
        with self.assertRaises(PermissionError):director.read(self.service,20,'lowstock',{})

    def test_named_client_edit_and_selected_excel_http_routes(self):
        status,groups=self.call('/director-api/report-categories');self.assertEqual(status,200);self.assertEqual(len(groups),19)
        self.assertEqual(self.call('/director-api/report-categories',authorized=False)[0],403)
        data={'name':'HTTP client','phone':'+998901234567','address':'Office','note':'Note','owner':20}
        status,response=self.action('director_client_save',data);self.assertEqual(status,200);ref=response['id']
        status,card=self.call('/director-api/clients?id='+str(ref));self.assertEqual(status,200);row=card['client'][0]
        changed={**data,'name':'Changed HTTP client','client':ref,'revision':row['revision']}
        self.assertEqual(self.action('director_client_save',changed,csrf=False)[0],403)
        self.assertEqual(self.action('director_client_save',changed)[0],200)
        self.assertEqual(self.action('director_client_save',{**changed,'name':'Stale'})[0],400)
        status,raw=self.call('/director-api/report?categories=clients,stock');self.assertEqual(status,200)
        wb=load_workbook(io.BytesIO(raw));self.assertEqual(len(wb.sheetnames),5)
        self.assertEqual(self.call('/director-api/report?categories=unknown')[0],400)
        self.assertEqual(self.call('/director-api/report?categories=clients',authorized=False)[0],403)
