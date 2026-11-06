"""Section views must retain original accounting ownership, stock and currency."""
import io
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from core import Store,now
from miniapp import MiniService,initialize
from director import read
from director_reports import build
from reports import workbook

class DirectorSectionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';self.s=Store(self.path);self.s.configure([10],[20]);initialize(self.path);self.api=MiniService(self.s,'fixture');self.today=now()[:10];self.q={'start':self.today,'end':self.today}
  with self.s.db:
   self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Tyre','125');self.client=self.s.client(20,'Client','+998901234567','','');self.vendor=self.s.supplier_save(10,'Factory');self.s.move(20,self.product,self.point,5,'in','Original')
 def tearDown(self):self.s.db.close();self.temp.cleanup()
 def view(self,kind,**q):return read(self.api,10,kind,{**self.q,**q})
 def receive(self):
  return self.api.write(10,'sections-receive-001','supplier_income',{'product':self.product,'supplier':self.vendor,'cost':'50','allocations':[{'point':self.point,'qty':4}],'currency':'USD','date':self.today})['id']
 def test_all_section_reads_director_only_and_do_not_write(self):
  before=self.s.db.total_changes
  for kind in ('products','expenses','customer_returns','supplier_returns','receipts','payments'):
   self.view(kind)
   with self.assertRaises(PermissionError):read(self.api,20,kind,self.q)
  self.assertEqual(self.s.db.total_changes,before)
 def test_products_independent_of_warehouse_and_legacy_price_not_relabelled(self):
  with self.s.db:
   second=self.s.product(10,'Legacy unknown','10');self.s.db.execute("UPDATE products SET currency='UZS',price_pending=1 WHERE id=?",(second,))
  items=self.view('products')['items'];self.assertEqual(len(items),2)
  row=next(r for r in items if r['id']==second);self.assertIsNone(row['price']);self.assertEqual(row['currency'],'UZS')
  self.assertEqual(self.view('products',currency='USD')['total'],1)
 def test_receipt_sources_do_not_double_count_supplier_moves_or_invent_cost(self):
  self.receive();self.assertEqual(self.view('receipts')['total'],1)
  other=self.view('receipts',receipt_source='movements');self.assertEqual(other['total'],1);self.assertEqual(other['items'][0]['qty'],5);self.assertNotIn('cost',other['items'][0]);self.assertNotIn('currency',other['items'][0])
  with self.assertRaises(ValueError):self.view('receipts',receipt_source='wrong')
 def test_expenses_reuse_manager_account_and_link_supplier_payment_once(self):
  self.receive()
  self.api.write(10,'sections-fund-0001','manager_record',{'manager':20,'kind':'fund','amount':'100','currency':'USD'})
  self.api.write(10,'sections-cost-0001','manager_record',{'manager':20,'kind':'expense','amount':'10','note':'Fuel','currency':'USD'})
  self.api.write(10,'sections-pay-00001','supplier_payment',{'supplier':self.vendor,'manager':20,'amount':'20','currency':'USD','method':'card'})
  expenses=self.view('expenses');self.assertEqual(expenses['total'],2);self.assertEqual(sum(r['amount'] for r in expenses['items']),3000);self.assertEqual(self.view('expenses',supplier=str(self.vendor))['total'],1)
  balance=next(r for r in self.s.manager_account(10)['balances'] if r['manager']==20);self.assertEqual(balance['balance'],7000)
  self.assertEqual(self.s.suppliers(10)['balances'][0]['balance'],18000)
 def test_full_customer_return_keeps_original_payments_and_restores_stock(self):
  sale=self.api.write(20,'sections-sale-0001','sell',{'client':self.client,'point':self.point,'items':[{'product':self.product,'qty':2,'price':'125'}],'payment':'card','paid':'50'})['id']
  self.assertEqual(self.view('payments',method='card')['total'],1)
  self.api.write(10,'sections-cancel-001','cancel_sale',{'sale':sale,'reason':'Returned','settlement':True,'expected_paid':5000})
  rows=self.view('customer_returns')['items'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['amount'],5000);self.assertEqual(rows[0]['items'][0]['qty'],2)
  self.assertEqual(self.view('payments')['total'],1);self.assertEqual(self.s.db.execute('SELECT qty FROM stock').fetchone()[0],5)
 def test_supplier_return_existing_idempotency_and_real_cost(self):
  self.receive();lot=self.s.rows('SELECT id FROM inventory_lots WHERE receipt IS NOT NULL')[0]['id'];d={'lot':lot,'qty':1,'note':'Defect'}
  first=self.api.write(10,'sections-return-01','supplier_return',d);self.assertEqual(first,self.api.write(10,'sections-return-01','supplier_return',d))
  rows=self.view('supplier_returns')['items'];self.assertEqual(len(rows),1);self.assertEqual((rows[0]['qty'],rows[0]['amount'],rows[0]['cost']),(1,5000,5000));self.assertEqual(rows[0]['supplier_name'],'Factory');self.assertEqual(self.s.suppliers(10)['balances'][0]['balance'],15000)
 def test_new_export_categories_have_real_rows_and_no_internal_identifiers(self):
  self.receive();self.api.write(10,'sections-fund-0002','manager_record',{'manager':20,'kind':'fund','amount':'100'});self.api.write(10,'sections-cost-0002','manager_record',{'manager':20,'kind':'expense','amount':'5','note':'Fuel'})
  data=build(self.s,10,{**self.q,'categories':'products,expenses,customer_returns,supplier_returns,receipts'});self.assertEqual(len(data['expenses']),1);self.assertEqual(len(data['other_incomes']),1);self.assertEqual(len(data['receipts']),1)
  book=load_workbook(io.BytesIO(workbook(data,hide_ids=True)));self.assertEqual(len(book.sheetnames),7)
  for rows in data.values():
   for row in rows:self.assertFalse(any(k in row for k in ('id','actor','manager','supplier','product','token')))
