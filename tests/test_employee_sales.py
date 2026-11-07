import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from core import Store,now
from miniapp import MiniService,MiniServer,initialize
from employee_sales import history,bot_sale_text
from test_miniapp import TOKEN,signed
from bot import Bot

class EmployeeSalesTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';self.s=Store(self.path);self.s.configure([10],[20,21]);initialize(self.path);self.api=MiniService(self.s,TOKEN);self.today=now()[:10]
  with self.s.db:
   self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Own tyre','125');self.s.move(20,self.product,self.point,200,'in','Fixture');self.shared=self.s.client(10,'Shared customer','+998901234567','','');self.other=self.s.client(21,'Secret customer','+998907654321','','');self.mine=self.s.client(20,'My contact','+998901112233','','')
   self.a=self.s.order(20,self.shared,[dict(product=self.product,qty=2,price='125')],point=self.point,paid='50',payment='card');self.b=self.s.order(21,self.shared,[dict(product=self.product,qty=1,price='999')],point=self.point,paid='1',payment='cash');self.secret=self.s.order(21,self.other,[dict(product=self.product,qty=1,price='888')],point=self.point,paid='0',payment='cash')
  self.server=MiniServer(('127.0.0.1',0),self.path,TOKEN,'https://cabinet.test');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_address[1])
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.s.db.close();self.temp.cleanup()
 def get(self,path,uid=20,auth=True):
  headers={'X-Telegram-Init-Data':signed(uid)} if auth else {}
  try:
   with urlopen(Request(self.base+path,headers=headers),timeout=20) as r:return r.status,json.loads(r.read())
  except HTTPError as r:return r.code,json.loads(r.read())
 def test_api_only_authenticated_actor_even_with_tampered_scope(self):
  for suffix in ('','?employee=21&actor=21&owner=21','?manager=21'):
   code,d=self.get('/api/my-sales'+suffix);self.assertEqual(code,200);self.assertEqual([r['id'] for r in d['items']],[self.a]);self.assertEqual([c['id'] for c in d['clients']],[self.shared]);self.assertNotIn('Secret customer',json.dumps(d));self.assertEqual(d['summary'][0]['debt_to_date'],20000)
  self.assertEqual(self.get('/api/my-sales?sale='+str(self.b))[0],403)
  self.assertEqual(self.get('/api/my-sales?client='+str(self.other))[1]['total'],0)
  self.assertEqual(self.get('/api/my-sales',auth=False)[0],403)
 def test_director_selected_staff_history_and_employee_url_rejected(self):
  with self.assertRaises(PermissionError):history(self.s,20,{},employee=21)
  self.assertEqual(history(self.s,10,{},employee=21)['total'],2)
  self.assertEqual(self.get('/director-api/employee-sales?employee=21',20)[0],403)
 def test_legacy_api_debts_export_and_client_card_never_mix_shared_client_sales(self):
  self.assertEqual([r['id'] for r in self.get('/api/sales?actor=21')[1]],[self.a]);self.assertEqual([r['id'] for r in self.get('/api/debts')[1]],[self.a])
  card=self.s.client_card(20,self.shared);self.assertEqual([r['id'] for r in card['sales']],[self.a]);self.assertEqual([r['id'] for r in self.s.report(20,self.today,self.today)['sales']],[self.a])
  with self.assertRaises(PermissionError):self.s.client_card(20,self.other)
  self.assertEqual(len(self.s.client_card(10,self.shared)['sales']),2)
 def test_customer_owner_change_does_not_transfer_historical_sales(self):
  with self.s.db:self.s.db.execute('UPDATE clients SET owner=21 WHERE id=?',(self.shared,))
  self.assertEqual(history(self.s,20,{})['items'][0]['id'],self.a)
  mine=self.get('/api/clients?scope=mine')[1]['items'];self.assertEqual({r['id'] for r in mine},{self.shared,self.mine})
 def test_goods_actual_paid_debt_due_and_payments_later_than_sale(self):
  with self.s.db:
   self.s.set_debt_due(20,self.a,'2027-01-10');self.s.payment(10,self.a,'25','cash');self.s.db.execute("UPDATE sales SET created='2026-01-01T23:59:59+05:00' WHERE id=?",(self.a,));self.s.db.execute("UPDATE payments SET created='2026-02-01T00:00:00+05:00' WHERE sale=?",(self.a,))
  data=history(self.s,20,{'start':'2026-01-01','end':'2026-01-01'});r=data['items'][0]
  self.assertEqual((r['total'],r['paid'],r['debt']),(25000,7500,17500));self.assertEqual(r['items'][0]['qty'],2);self.assertEqual(r['items'][0]['price'],12500);self.assertEqual(r['debt_due'],'2027-01-10');self.assertEqual(data['days'][0]['date'],'2026-01-01');self.assertEqual(data['days'][0]['paid_to_date'],7500);self.assertEqual(len(r['payments']),2)
 def test_date_boundaries_filters_and_pagination_above_100(self):
  with self.s.db:
   self.s.db.execute("UPDATE sales SET created='2026-01-02T00:00:00+05:00' WHERE id=?",(self.a,))
   for i in range(102):self.s.order(20,self.mine,[dict(product=self.product,qty=1,price='1')],point=self.point,paid='1',payment='cash')
  self.assertEqual(history(self.s,20,{'start':'2026-01-01','end':'2026-01-01'})['total'],0)
  self.assertEqual(history(self.s,20,{'start':'2026-01-02','end':'2026-01-02'})['total'],1)
  first=history(self.s,20,{});last=history(self.s,20,{'page':'5'});self.assertEqual(first['total'],103);self.assertEqual(len(first['items']),20);self.assertEqual(len(last['items']),3);self.assertEqual(first['summary'][0]['sales_count'],103)
  self.assertEqual(history(self.s,20,{'payment_status':'paid'})['total'],102);self.assertEqual(history(self.s,20,{'payment_status':'debt'})['total'],1)
  self.assertEqual(history(self.s,20,{'q':'Secret customer'})['total'],0)
  with self.assertRaises(ValueError):history(self.s,20,{'start':'2026-01-03','end':'2026-01-02'})
 def test_cancelled_sale_zero_debt_original_payments_and_refund_preserved(self):
  with self.s.db:self.s.cancel_sale(10,self.a,'Full return',refund_confirmed=True)
  d=history(self.s,20,{});r=d['items'][0];self.assertEqual(r['debt'],0);self.assertEqual(r['paid'],5000);self.assertEqual(r['refunds'][0]['amount'],5000);self.assertEqual(d['summary'][0]['sales_total'],0);self.assertEqual(d['summary'][0]['cancelled_count'],1);self.assertEqual(history(self.s,20,{'payment_status':'debt'})['total'],0)
 def test_currency_summaries_separate_and_no_private_fields(self):
  with self.s.db:
   sale=self.s.order(20,self.mine,[dict(product=self.product,qty=1,price='10')],point=self.point,paid='0',payment='cash');self.s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(sale,))
  d=history(self.s,20,{});self.assertEqual({r['currency']:r['sales_total'] for r in d['summary']},{'USD':25000,'UZS':1000});self.assertEqual(history(self.s,20,{'currency':'USD'})['total'],1)
  for row in d['items']:self.assertFalse(any(k in row for k in ('cost','profit','supplier','token','actor','owner')))
 def test_inactive_employee_denied_and_inactive_staff_history_retained_for_director(self):
  with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
  self.assertEqual(self.get('/api/my-sales')[0],403)
  with self.assertRaises(PermissionError):history(self.s,20,{})
  self.assertEqual(history(self.s,10,{},employee=20)['total'],1)
 def test_bot_sales_and_card_export_scoped_and_human_money(self):
  bot=Bot(self.s);bot.show_records(20,'sales');texts=[json.loads(r['payload']).get('text','') for r in self.s.rows('SELECT payload FROM outbox WHERE chat=20')];text='\n'.join(texts)
  self.assertIn('Own tyre × 2',text);self.assertIn('200.00 USD',text);self.assertNotIn('999.00',text);self.assertNotIn('Secret customer',text)
  with self.assertRaises(PermissionError):bot_sale_text(self.s,20,{'id':self.b,'client_name':'Shared'},'uz')

 def test_missing_historical_payment_warns_without_fabricating_receipt(self):
  with self.s.db:self.s.db.execute('DELETE FROM payments WHERE sale=?',(self.a,))
  r=history(self.s,20,{})['items'][0];self.assertFalse(r['payment_history_complete']);self.assertEqual(r['paid'],5000);self.assertEqual(r['payments'],[])
 def test_shared_client_other_employee_refund_is_not_in_client_card(self):
  with self.s.db:self.s.cancel_sale(10,self.b,'Other employee return',refund_confirmed=True)
  self.assertEqual(self.s.client_card(20,self.shared)['refunds'],[])
  self.assertEqual(len(self.s.client_card(21,self.shared)['refunds']),1)
