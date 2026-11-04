import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from openpyxl import load_workbook
from core import Store,now
from miniapp import MiniService,MiniServer,initialize
from director_analytics import analytics,for_api,line_amount
from director_reports import build
from reports import workbook
import director_auth as auth

class DirectorAnalyticsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';self.s=Store(self.path);self.s.configure([10],[20,21]);initialize(self.path);self.service=MiniService(self.s,'fixture');self.today=now()[:10]
  with self.s.db:
   self.point=self.s.add('points',name='Warehouse');self.target=self.s.add('points',name='Showroom');self.a=self.s.product(10,'Tyre A','100.01');self.b=self.s.product(10,'Tyre B','50.02');self.client=self.s.client(20,'Buyer','+998901234567','','')
   for p in (self.a,self.b):
    self.s.move(20,p,self.point,100,'in','Fixture');self.s.move(20,p,self.target,10,'in','Fixture')
 def tearDown(self):self.s.db.close();self.temp.cleanup()
 def sell(self,actor=20,items=None,paid='0'):
  with self.s.db:return self.s.order(actor,self.client,items or [dict(product=self.a,qty=1,price='100.01')],point=self.point,paid=paid,payment='card')
 def data(self,start=None,end=None):return analytics(self.s,10,start or self.today,end or self.today)
 def test_multi_product_invoice_separate_locations_no_duplicate_sales_totals(self):
  self.sell(items=[dict(product=self.a,qty=2,price='100.01',point=self.point),dict(product=self.a,qty=1,price='100.01',point=self.target),dict(product=self.b,qty=2,price='50.02')],paid='50')
  d=self.data();p={r['product']:r for r in d['products']};e=d['employees'][0]
  self.assertEqual((p[self.a]['qty'],p[self.a]['sales_count'],p[self.a]['revenue']),(3,1,30003));self.assertEqual(p[self.b]['revenue'],10004)
  self.assertEqual((e['sales_count'],e['qty'],e['revenue'],e['paid_to_date'],e['debt_to_date'],e['client_count']),(1,5,40007,5000,35007,1));self.assertEqual(sum(r['revenue'] for r in p.values()),e['revenue']);self.assertNotIn('debt_to_date',p[self.a])
 def test_cancelled_sales_and_non_sale_stock_events_excluded(self):
  one=self.sell(paid='10');self.sell(actor=21)
  with self.s.db:self.s.cancel_sale(10,one,'Return',refund_confirmed=True)
  self.service.write(10,'analytics-transfer-001','stock_transfer',{'product':self.a,'source':self.point,'target':self.target,'qty':5,'reason':'Move'})
  d=self.data();self.assertEqual(len(d['employees']),1);self.assertEqual(d['employees'][0]['employee'],21);self.assertEqual(d['products'][0]['qty'],1);self.assertEqual(d['products'][0]['revenue'],10001)
 def test_period_boundaries_and_current_paid_separate_from_period_receipts(self):
  one=self.sell()
  with self.s.db:
   self.s.db.execute("UPDATE sales SET created='2026-01-01T23:59:59+05:00' WHERE id=?",(one,));self.s.payment(10,one,'10','cash');self.s.db.execute("UPDATE payments SET created='2026-02-01T00:00:00+05:00' WHERE sale=?",(one,))
  d=self.data('2026-01-01','2026-01-01');self.assertEqual(d['employees'][0]['paid_to_date'],1000);self.assertEqual(d['employees'][0]['debt_to_date'],9001);self.assertEqual(self.data('2026-01-02','2026-01-02')['products'],[])
  with self.assertRaises(ValueError):self.data('2026-01-02','2026-01-01')
 def test_original_currencies_and_inactive_staff_products_are_preserved(self):
  one=self.sell();self.sell(actor=21)
  with self.s.db:
   self.s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(one,));self.s.db.execute('UPDATE products SET active=0 WHERE id=?',(self.a,));self.s.db.execute('UPDATE users SET active=0 WHERE id=21')
  d=self.data();self.assertEqual({r['currency'] for r in d['products']},{'USD','UZS'});self.assertEqual({r['currency']:r['revenue'] for r in d['products']},{'USD':10001,'UZS':10001});self.assertEqual(next(r for r in d['employees'] if r['employee']==21)['active'],0)
 def test_same_names_do_not_merge_distinct_products(self):
  self.sell(items=[dict(product=self.a,qty=1,price='10'),dict(product=self.b,qty=1,price='20')])
  with self.s.db:self.s.db.execute("UPDATE products SET name='Same name' WHERE id IN (?,?)",(self.a,self.b))
  self.assertEqual(len(self.data()['products']),2)
 def test_historical_discount_rounds_half_even_in_exact_cents(self):
  one=self.sell(items=[dict(product=self.a,qty=1,price='0.01'),dict(product=self.b,qty=1,price='0.03')])
  with self.s.db:self.s.db.execute('UPDATE sale_items SET discount=50 WHERE sale=?',(one,));self.s.db.execute('UPDATE sales SET total=2 WHERE id=?',(one,))
  d=self.data();self.assertEqual(d['review_sales_count'],0);self.assertEqual({r['product']:r['revenue'] for r in d['products']},{self.a:0,self.b:2})
 def test_mismatched_lines_unknown_revenue_never_allocate_invoice_or_debt(self):
  one=self.sell(items=[dict(product=self.a,qty=1,price='10'),dict(product=self.a,qty=1,price='10',point=self.target),dict(product=self.b,qty=1,price='20')])
  with self.s.db:self.s.db.execute('UPDATE sales SET total=5000 WHERE id=?',(one,))
  d=self.data();self.assertEqual(d['review_sales_count'],1);self.assertEqual(d['review_by_currency'],{'USD':1});self.assertTrue(all(r['revenue'] is None and r['unknown_sales_count']==1 for r in d['products']));self.assertEqual(d['employees'][0]['revenue'],5000)
 def test_missing_legacy_lines_visible_as_review_not_zero_quantity(self):
  with self.s.db:self.s.add('sales',client=self.client,point=self.point,actor=20,total=1000,paid=0,payment='cash',created=now())
  d=self.data();self.assertEqual(d['products'],[]);self.assertIsNone(d['employees'][0]['qty']);self.assertEqual(d['review_sales_count'],1)
  export=build(self.s,10,dict(start=self.today,end=self.today,categories='product_analytics'));self.assertEqual(export['analytics_review'][0]['review_sales_count'],1)
 def test_read_only_permission_and_big_integer_api_string_precision(self):
  self.sell(items=[dict(product=self.a,qty=90,price='1000000000000')]);self.sell(items=[dict(product=self.a,qty=1,price='71992547409.93')]);before=self.s.db.total_changes;d=self.data();self.assertEqual(self.s.db.total_changes,before)
  self.assertEqual(d['employees'][0]['revenue'],9007199254740993);self.assertEqual(for_api(d)['products'][0]['revenue'],'9007199254740993')
  exported=build(self.s,10,dict(start=self.today,end=self.today,categories='employee_analytics'));book=load_workbook(io.BytesIO(workbook(exported,hide_ids=True)));self.assertIn('90071992547409.93',[c.value for row in book.worksheets[0] for c in row])
  with self.assertRaises(PermissionError):analytics(self.s,20,self.today,self.today)
 def test_selected_excel_contains_two_analyses_without_identifiers_or_profit(self):
  self.sell(paid='20');d=build(self.s,10,dict(start=self.today,end=self.today,categories='product_analytics,employee_analytics'));self.assertEqual(set(d),{'product_analytics','employee_analytics','analytics_review'});self.assertEqual(d['product_analytics'][0]['revenue'],10001)
  for rows in d.values():
   for r in rows:self.assertFalse(any(k in r for k in ('id','employee','product','cost','profit','token')))
  book=load_workbook(io.BytesIO(workbook(d,hide_ids=True)));self.assertEqual(len(book.sheetnames),3);self.assertIn(100.01,[c.value for row in book['Tovarlar tahlili'] for c in row])
 def test_http_auth_and_overview_both_share_same_analytics(self):
  self.sell();self.sell(actor=21)
  with self.s.db:token=auth.issue(self.s,10)
  server=MiniServer(('127.0.0.1',0),self.path,'fixture','https://cabinet.test');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1])
  def get(path,cookie=True):
   try:
    with urlopen(Request(base+path,headers={'Cookie':auth.COOKIE+'='+token} if cookie else {})) as r:return r.status,json.loads(r.read())
   except HTTPError as e:return e.code,json.loads(e.read())
  try:
   self.assertEqual(get('/director-api/analytics',False)[0],403);code,d=get('/director-api/analytics');self.assertEqual(code,200);overview=get('/director-api/overview')[1];self.assertEqual(d['products'],overview['analytics']['products']);self.assertIsInstance(d['employees'][0]['revenue'],str)
   with self.s.db:self.s.db.execute('UPDATE users SET role=\'employee\' WHERE id=10')
   self.assertEqual(get('/director-api/analytics')[0],403)
  finally:server.shutdown();server.server_close();thread.join()
