import io
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from core import Store,now
from miniapp import MiniService,initialize
from director_business import save_client,revision,client_list,client_card,supplier_card,filtered
from director_reports import build,GROUPS
from reports import workbook
import director

class DirectorBusinessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'db');self.s.configure([10],[20]);initialize(Path(self.tmp.name)/'db');self.service=MiniService(self.s,'fixture');self.date=now()[:10]
  with self.s.db:
   self.point=self.s.add('points',name='Ombor');self.product=self.s.product(10,'Tire','125');self.s.move(20,self.product,self.point,20,'in','fixture');self.client=self.s.client(20,'Client','+998900000000','Address','Note');self.vendor=self.s.supplier_save(10,'Factory')
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def save(self,**d):return save_client(self.s,10,dict(name='New client',phone='+998901234567',address='Office',note='Comment',owner=20,**d))
 def test_create_edit_retains_sales_and_conflicting_edits_fail(self):
  ref=self.save();row=self.s.one('clients',ref)
  with self.s.db:sale=self.s.order(20,ref,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='25',payment='card')
  before=self.s.one('sales',sale);version=revision(row)
  save_client(self.s,10,{**row,'client':ref,'revision':version,'name':'Renamed'})
  self.assertEqual(self.s.one('sales',sale),before);self.assertEqual(self.s.one('clients',ref)['name'],'Renamed')
  with self.assertRaisesRegex(ValueError,'client_changed'):save_client(self.s,10,{**row,'client':ref,'revision':version})
 def test_employee_inactive_owner_and_invalid_phone_denied(self):
  with self.assertRaises(PermissionError):save_client(self.s,20,{'name':'X'})
  with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
  with self.assertRaises(PermissionError):self.save()
  with self.assertRaises(ValueError):save_client(self.s,10,dict(name='X',phone='bad',owner=10))
 def test_client_debt_history_and_opening_not_aggregate(self):
  with self.s.db:
   sale=self.s.order(20,self.client,[dict(product=self.product,qty=2,price='125')],point=self.point,paid='50',payment='card');self.s.payment(20,sale,'25','cash')
  card=client_card(self.s,10,self.client,self.date,self.date)
  self.assertEqual([r['balance_after'] for r in card['ledger']['entries']],[25000,20000,17500]);self.assertEqual(card['history_review_count'],0)
  old=client_card(self.s,10,self.client,'2100-01-01','2100-01-01');self.assertEqual(old['ledger']['opening'][0]['balance'],17500)
  self.assertEqual(len(client_list(self.s,10,{'debt_status':'debt'})),1)
  self.assertEqual(len(client_list(self.s,10,{'debt_status':'clear'})),0)
 def test_supplier_history_2500_1000_500_and_opening(self):
  with self.s.db:
   self.s.receive(20,self.product,self.vendor,'250',[dict(point=self.point,qty=10)],'Invoice',self.date,'USD');self.s.supplier_pay(10,self.vendor,'1000','cash',self.date);self.s.supplier_pay(10,self.vendor,'500','card',self.date)
  card=supplier_card(self.s,10,self.vendor,self.date,self.date)
  self.assertEqual([r['balance_after'] for r in card['ledger']['entries']],[250000,150000,100000]);self.assertEqual(card['totals'][0]['balance'],100000)
  self.assertEqual(supplier_card(self.s,10,self.vendor,'2100-01-01','2100-01-01')['ledger']['opening'][0]['balance'],100000)
 def test_named_stock_filters_and_unknown_quantities(self):
  q=dict(start=self.date,end=self.date,point=str(self.point),stock_status='available');data=director.read(self.service,10,'stock',q);self.assertEqual(data['total'],1)
  self.assertEqual(director.read(self.service,10,'stock',{**q,'point':'999'})['total'],0)
  self.assertEqual(len(filtered([{'qty':None},{'qty':0},{'qty':2}],{'stock_status':'unknown'})),1)
 def test_selected_reports_all_groups_no_ids_no_tokens(self):
  with self.s.db:
   self.s.receive(20,self.product,self.vendor,'250',[dict(point=self.point,qty=10)],'Invoice',self.date,'USD');self.s.supplier_pay(10,self.vendor,'1000','cash',self.date)
  q=dict(start=self.date,end=self.date,categories='clients,suppliers,stock');data=build(self.s,10,q)
  self.assertEqual(set(data),set(GROUPS['clients'][1]+GROUPS['suppliers'][1]+GROUPS['stock'][1]))
  book=load_workbook(io.BytesIO(workbook(data,hide_ids=True)));self.assertGreater(len(book.sheetnames),5)
  for ws in book:
   self.assertNotIn('ID',[c.value for c in ws[1]])
  all_data=build(self.s,10,{**q,'categories':'all'});self.assertEqual(set(all_data),{x for _,groups in GROUPS.values() for x in groups})
  workbook(all_data,hide_ids=True)
  for rows in all_data.values():
   for r in rows:self.assertFalse(any(k in r for k in ('id','actor','client','supplier','manager','token','revision')))
  for value in ('','invalid','stock,invalid'):
   with self.assertRaises(ValueError):build(self.s,10,{**q,'categories':value})
 def test_client_save_uses_existing_idempotency_and_director_permission(self):
  d=dict(name='Created once',phone='',address='',note='',owner=20)
  a=self.service.write(10,'client-save-once-01','director_client_save',d);b=self.service.write(10,'client-save-once-01','director_client_save',d);self.assertEqual(a,b)
  self.assertEqual(len(self.s.rows("SELECT * FROM clients WHERE name='Created once'")),1)
  with self.assertRaises(PermissionError):self.service.write(20,'client-save-denied-01','director_client_save',d)

 def test_cancelled_sale_history_returns_to_zero_and_missing_receipt_flag(self):
  with self.s.db:
   sale=self.s.order(20,self.client,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='25',payment='cash');self.s.cancel_sale(10,sale,'Returned',refund_confirmed=True)
  card=client_card(self.s,10,self.client,self.date,self.date)
  self.assertEqual(card['ledger']['period_closing'][0]['balance'],0);self.assertEqual(card['debts'],[])
  with self.s.db:self.s.db.execute('DELETE FROM payments WHERE sale=?',(sale,))
  self.assertEqual(client_card(self.s,10,self.client,self.date,self.date)['history_review_count'],1)
 def test_backdated_supplier_entries_and_currencies_keep_separate_balances(self):
  with self.s.db:
   self.s.receive(20,self.product,self.vendor,'10',[dict(point=self.point,qty=1)],'USD receipt','2026-01-02','USD');self.s.supplier_pay(10,self.vendor,'3','cash','2026-01-01','USD');self.s.receive(20,self.product,self.vendor,'1000',[dict(point=self.point,qty=1)],'Legacy UZS','2026-01-01','UZS')
  ledger=supplier_card(self.s,10,self.vendor,'2026-01-02','2026-01-02')['ledger']
  self.assertEqual({r['currency']:r['balance'] for r in ledger['opening']},{'USD':-300,'UZS':100000});self.assertEqual(ledger['entries'][0]['balance_after'],700)
 def test_current_stock_and_debt_survive_historical_report_period(self):
  with self.s.db:self.s.order(20,self.client,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='25',payment='card')
  data=build(self.s,10,dict(start='2000-01-01',end='2000-01-01',categories='sales,stock,debts'))
  self.assertEqual(data['sales'],[]);self.assertEqual(data['stock'][0]['qty'],19);self.assertEqual(data['current_debts'][0]['debt'],10000)
