"""Qarzlar: supplier payment deadlines, late days and per-currency totals."""
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from core import Store,now
from miniapp import MiniService,initialize
from director import read,late_days


class DebtsSectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db'
        self.s=Store(self.path);self.s.configure([10],[20]);initialize(self.path);self.api=MiniService(self.s,'fixture')
        self.today=now()[:10];self.q={'start':self.today,'end':self.today}
        with self.s.db:
            self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Tyre','125')
            self.client=self.s.client(20,'Debtor','+998901234567','','');self.vendor=self.s.supplier_save(10,'Factory')
        self.api.write(10,'debts-receive-001','supplier_income',{'product':self.product,'supplier':self.vendor,'cost':'50','allocations':[{'point':self.point,'qty':4}],'currency':'USD','date':self.today})

    def tearDown(self):
        self.s.db.close();self.temp.cleanup()

    def view(self,kind,**q):return read(self.api,10,kind,{**self.q,**q})
    def ago(self,days):return (date.fromisoformat(self.today)-timedelta(days=days)).isoformat()

    def test_late_days_counts_whole_days_only_when_overdue(self):
        self.assertEqual(late_days('',self.today),0)
        self.assertEqual(late_days(self.today,self.today),0)
        self.assertEqual(late_days(self.ago(-3),self.today),0)
        self.assertEqual(late_days(self.ago(5),self.today),5)

    def test_payables_show_what_we_owe_with_total_and_no_due_date_yet(self):
        data=self.view('payables')
        self.assertEqual(data['total'],1)
        row=data['items'][0]
        self.assertEqual((row['supplier_name'],row['currency'],row['debt_due'],row['late_days']),('Factory','USD','',0))
        self.assertGreater(row['owed'],0)
        self.assertEqual(data['totals'],[{'currency':'USD','amount':row['owed']}])

    def test_payables_are_director_only(self):
        with self.assertRaises(PermissionError):read(self.api,20,'payables',self.q)

    def test_due_date_makes_payable_overdue_and_can_be_cleared(self):
        self.api.write(10,'debts-due-000001','supplier_due',{'supplier':self.vendor,'currency':'USD','due':self.ago(7)})
        row=self.view('payables')['items'][0]
        self.assertEqual((row['debt_due'],row['late_days']),(self.ago(7),7))
        self.assertEqual(self.view('payables',overdue='1')['total'],1)
        self.api.write(10,'debts-due-000002','supplier_due',{'supplier':self.vendor,'currency':'USD','due':self.ago(-10)})
        self.assertEqual(self.view('payables',overdue='1')['total'],0)
        self.api.write(10,'debts-due-000003','supplier_due',{'supplier':self.vendor,'currency':'USD','due':''})
        self.assertEqual(self.view('payables')['items'][0]['debt_due'],'')

    def test_due_date_validation_and_permission(self):
        with self.assertRaises(PermissionError):self.api.write(20,'debts-due-000004','supplier_due',{'supplier':self.vendor,'currency':'USD','due':self.today})
        for data in ({'supplier':self.vendor,'currency':'USD','due':'31.12.2026'},{'supplier':self.vendor,'currency':'EUR','due':self.today},{'supplier':99999,'currency':'USD','due':self.today}):
            with self.assertRaises((ValueError,LookupError)):self.api.write(10,'debts-due-bad-'+str(len(data['due'])),'supplier_due',data)

    def test_paid_supplier_disappears_from_payables(self):
        owed=self.view('payables')['items'][0]['owed']
        from core import fmt
        self.s.supplier_pay(10,self.vendor,fmt(owed).replace(' ',''),'full',self.today,'USD')
        self.assertEqual(self.view('payables')['total'],0)
        self.assertEqual(self.view('payables')['totals'],[])

    def test_customer_debts_have_late_days_filter_and_totals(self):
        sale=self.s.order(20,self.client,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='25',payment='cash')
        self.s.set_debt_due(20,sale,self.ago(4))
        data=self.view('debts')
        self.assertEqual(data['total'],1)
        self.assertEqual(data['items'][0]['late_days'],4)
        self.assertEqual(data['totals'],[{'currency':data['items'][0]['currency'],'amount':data['items'][0]['debt']}])
        self.assertEqual(self.view('debts',overdue='1')['total'],1)
        self.s.set_debt_due(20,sale,self.ago(-4))
        self.assertEqual(self.view('debts',overdue='1')['total'],0)
        self.assertEqual(self.view('debts')['items'][0]['late_days'],0)


if __name__=='__main__':unittest.main()
