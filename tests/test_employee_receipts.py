import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from core import Store,now
from miniapp import MiniService,MiniServer,initialize
from employee_sales import history
from test_miniapp import signed,TOKEN

class EmployeeReceiptTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';self.s=Store(self.path);self.s.configure([10],[20,21]);initialize(self.path);self.api=MiniService(self.s,TOKEN)
  with self.s.db:
   self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Tyre','125');self.s.move(20,self.product,self.point,20,'in','Fixture');self.client=self.s.client(20,'Customer','+998901234567','','');self.sale=self.s.order(20,self.client,[dict(product=self.product,qty=2,price='125')],point=self.point,paid='50',payment='card');self.other=self.s.order(21,self.client,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='0',payment='cash')
 def tearDown(self):self.s.db.close();self.temp.cleanup()
 def collect(self,key='employee-collect-01',uid=20,**updates):
  d=dict(sale=self.sale,amount='50.25',payment='cash',expected_paid='5000');d.update(updates);return self.api.write(uid,key,'collect_debt',d)
 def test_partial_receipt_updates_original_payment_and_manager_once(self):
  before_stock=self.s.rows('SELECT * FROM stock');r=self.collect()['id'];self.assertEqual((r['amount_cents'],r['remaining_cents'],r['currency']),('5025','14975','USD'));self.assertEqual(self.s.one('sales',self.sale)['paid'],10025);self.assertEqual(self.s.rows('SELECT * FROM stock'),before_stock)
  p=self.s.rows('SELECT * FROM payments WHERE id=?',(r['payment'],))[0];self.assertEqual(p['actor'],20);self.assertEqual(p['amount'],5025);self.assertTrue(self.s.rows("SELECT * FROM audit WHERE action='payment' AND ref=?",(r['payment'],)))
  a=self.s.manager_account(10,20);self.assertEqual(a['balances'][0]['received'],10025);self.assertEqual(self.s.rows('SELECT * FROM manager_received'),[])
 def test_legacy_pay_and_core_cannot_collect_other_employee_sale(self):
  before={table:self.s.rows('SELECT * FROM '+table) for table in ('sales','payments','audit','outbox')}
  with self.assertRaises(PermissionError):
   self.api.write(20,'legacy-pay-denied-001','pay',dict(sale=self.other,amount='1',payment='cash'))
  with self.assertRaises(PermissionError),self.s.db:
   self.s.payment(20,self.other,'1','cash')
  for table,rows in before.items():self.assertEqual(self.s.rows('SELECT * FROM '+table),rows)
  self.api.write(10,'legacy-pay-director-1','pay',dict(sale=self.other,amount='1',payment='cash'))
  with self.s.db:self.s.db.execute("UPDATE users SET role='employee' WHERE id=10")
  with self.assertRaises(PermissionError):
   self.api.write(10,'legacy-pay-director-1','pay',dict(sale=self.other,amount='1',payment='cash'))
 def test_retries_same_key_never_double_receive(self):
  a=self.collect();self.assertEqual(self.collect(),a);self.assertEqual(len(self.s.rows('SELECT * FROM payments WHERE sale=?',(self.sale,))),2)
  with self.assertRaisesRegex(ValueError,'request_changed'):self.collect(amount='49')
 def test_strict_own_sale_and_permission_checked_before_cached_result(self):
  with self.assertRaises(PermissionError):self.collect(sale=self.other,expected_paid='0')
  # Directors can collect on any invoice. After role change, replay cannot bypass scope.
  self.collect(uid=10)
  with self.s.db:self.s.db.execute("UPDATE users SET role='employee' WHERE id=10")
  with self.assertRaises(PermissionError):self.collect(uid=10)
 def test_stale_preview_rejected_even_when_new_amount_would_fit(self):
  self.collect()
  with self.assertRaisesRegex(ValueError,'debt_changed'):self.collect(key='employee-stale-001',amount='10')
  self.assertEqual(self.s.one('sales',self.sale)['paid'],10025)
 def test_overpayment_zero_negative_precision_invalid_method_no_mutation(self):
  before=self.s.one('sales',self.sale)
  for i,change in enumerate([{'amount':'201'},{'amount':'0'},{'amount':'-1'},{'amount':'1.001'},{'payment':'crypto'},{'expected_paid':True},{'expected_paid':None},{'expected_paid':'5000.0'}]):
   with self.assertRaises(ValueError):self.collect(key=f'employee-invalid-{i:03}',**change)
  self.assertEqual(self.s.one('sales',self.sale),before);self.assertEqual(len(self.s.rows('SELECT * FROM payments WHERE sale=?',(self.sale,))),1)
 def test_full_collection_all_methods_and_history_has_collector(self):
  for n,(amount,method,expected) in enumerate([('50.25','cash','5000'),('49.75','card','10025'),('100','transfer','15000')]):self.collect(key=f'employee-method-{n:03}',amount=amount,payment=method,expected_paid=expected)
  self.assertEqual(self.s.debts(20),[]);r=history(self.s,20,{})['items'][0];self.assertEqual((r['paid_cents'],r['debt_cents']),('25000','0'));self.assertEqual(len(r['payments']),4);self.assertTrue(all('collector_name' in p for p in r['payments']))
  b=self.s.manager_account(10,20)['balances'][0];self.assertEqual((b['received_cash'],b['received_card'],b['received_transfer']),(5025,9975,10000))
 def test_cancelled_paid_and_deactivated_access_denied(self):
  with self.s.db:self.s.cancel_sale(10,self.sale,'Return',refund_confirmed=True)
  with self.assertRaisesRegex(ValueError,'sale_cancelled'):self.collect()
  with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
  with self.assertRaises(PermissionError):self.collect()
 def test_legacy_currency_and_server_collector_timestamp_not_forged(self):
  with self.s.db:self.s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(self.sale,));self.s.db.execute("UPDATE payments SET currency='UZS' WHERE sale=?",(self.sale,))
  r=self.collect(amount='10',currency='USD',actor=21,date='2000-01-01')['id'];self.assertEqual(r['currency'],'UZS');self.assertEqual(r['created'][:10],now()[:10]);p=self.s.rows('SELECT actor,currency FROM payments WHERE id=?',(r['payment'],))[0];self.assertEqual(p,{'actor':20,'currency':'UZS'})
 def test_payment_insert_failure_rolls_back_paid_even_direct_core_call(self):
  before=self.s.one('sales',self.sale);original=self.s.add
  def failing(table,**fields):
   if table=='payments':raise RuntimeError('insert failure')
   return original(table,**fields)
  with patch.object(self.s,'add',side_effect=failing):
   with self.assertRaises(RuntimeError):self.s.payment(20,self.sale,'10','cash')
  self.assertEqual(self.s.one('sales',self.sale),before)
 def test_parallel_confirmations_only_one_uses_preview(self):
  barrier=threading.Barrier(2);result=[]
  def pay(i):
   s=Store(self.path);api=MiniService(s,TOKEN)
   try:
    barrier.wait();api.write(20,f'employee-parallel-{i:03}','collect_debt',dict(sale=self.sale,amount='25',payment='cash',expected_paid='5000'));result.append('ok')
   except ValueError as e:result.append(str(e))
   finally:s.db.close()
  threads=[threading.Thread(target=pay,args=(i,)) for i in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertCountEqual(result,['ok','debt_changed']);self.assertEqual(self.s.one('sales',self.sale)['paid'],7500)
 def test_http_collection_auth_version_and_own_sale(self):
  server=MiniServer(('127.0.0.1',0),self.path,TOKEN,'https://cabinet.test');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1])
  def call(uid=20,version=2,sale=None,auth=True,key='employee-http-collect-01'):
   body=dict(cmd='collect_debt',data=dict(sale=sale or self.sale,amount='50.25',payment='cash',expected_paid='5000'),money_version=version);headers={'Content-Type':'application/json','Origin':'https://cabinet.test','Idempotency-Key':key}
   if auth:headers['X-Telegram-Init-Data']=signed(uid)
   try:
    with urlopen(Request(base+'/api/action',data=json.dumps(body).encode(),headers=headers)) as r:return r.status,json.loads(r.read())
   except HTTPError as e:return e.code,json.loads(e.read())
  try:
   self.assertEqual(call(auth=False)[0],403);self.assertEqual(call(version=1)[0],400);self.assertEqual(call(sale=self.other)[0],403);self.assertEqual(call()[0],200);self.assertEqual(call()[0],200);self.assertEqual(self.s.one('sales',self.sale)['paid'],10025)
   code,error=call(key='employee-http-stale-01');self.assertEqual(code,400);self.assertIn('yangilash',error['error'])
  finally:server.shutdown();server.server_close();thread.join()
 def test_later_debt_payment_is_todays_receipt_not_new_sale(self):
  with self.s.db:
   self.s.db.execute("UPDATE sales SET created='2026-01-01T10:00:00+05:00' WHERE id=?",(self.sale,));self.s.db.execute("UPDATE payments SET created='2026-01-01T10:00:00+05:00' WHERE sale=?",(self.sale,))
  self.collect();dashboard=self.api.dashboard(20,now()[:10],now()[:10]);self.assertEqual(dashboard['sales'],0);self.assertEqual(dashboard['total'],0);self.assertEqual(dashboard['received'],5025);self.assertEqual(dashboard['debt'],14975)
  old=history(self.s,20,dict(start='2026-01-01',end='2026-01-01'))['items'][0];self.assertEqual(old['paid'],10025);self.assertEqual(old['debt'],14975)
