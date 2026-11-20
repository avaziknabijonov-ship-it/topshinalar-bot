import tempfile,unittest
from pathlib import Path
from core import Store
from miniapp import MiniService,initialize
from director_sections import records


class ExpenseCategories(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'x.sqlite3'
        self.s=Store(self.path);self.s.configure([10],[20]);initialize(self.path);self.api=MiniService(self.s,'t')
        self.api.write(10,'expense-fund-key-0-padded','manager_record',{'manager':20,'kind':'fund','amount':'1000','currency':'USD','note':'fond','date':'2026-11-01'})
    def tearDown(self):self.tmp.cleanup()
    def test_category_flow(self):
        c=self.api.write(10,'expense-test-key-1-padded','expense_category',{'name':'Ijara'})['id']
        with self.assertRaises(ValueError):self.api.write(10,'expense-test-key-2-padded','expense_category',{'name':'ijara'})
        self.api.write(10,'expense-test-key-3-padded','manager_record',{'manager':20,'kind':'expense','amount':'10','currency':'USD','note':'oy','date':'2026-11-01','category':c})
        self.api.write(10,'expense-test-key-4-padded','manager_record',{'manager':20,'kind':'expense','amount':'5','currency':'USD','note':'boshqa','date':'2026-11-01'})
        rows=records(self.s,10,'expenses','2026-11-01','2026-11-30',{})
        self.assertEqual(sorted(r['category_name'] or '' for r in rows),['','Ijara'])
        self.assertEqual(records(self.s,10,'expenses','2026-11-01','2026-11-30',{'expense_type':'supplier'}),[])
        self.assertEqual(len(records(self.s,10,'expenses','2026-11-01','2026-11-30',{'expense_type':'operating'})),2)
        only=records(self.s,10,'expenses','2026-11-01','2026-11-30',{'category':str(c)})
        self.assertEqual(len(only),1)
    def test_rules(self):
        c=self.api.write(10,'expense-test-key-1-padded','expense_category',{'name':'Yo‘l'})['id']
        with self.assertRaises(Exception):self.api.write(20,'expense-test-key-2-padded','expense_category',{'name':'X'})
        with self.assertRaises(ValueError):self.api.write(10,'expense-test-key-3-padded','manager_record',{'manager':20,'kind':'fund','amount':'10','currency':'USD','note':'x','date':'2026-11-01','category':c})
        with self.assertRaises(ValueError):self.api.write(10,'expense-test-key-4-padded','manager_record',{'manager':20,'kind':'expense','amount':'10','currency':'USD','note':'x','date':'2026-11-01','category':999})
        self.api.write(10,'expense-test-key-5-padded','expense_category',{'category':c,'name':'Yo‘l','active':'0'})
        with self.assertRaises(ValueError):self.api.write(10,'expense-test-key-6-padded','manager_record',{'manager':20,'kind':'expense','amount':'10','currency':'USD','note':'x','date':'2026-11-01','category':c})


if __name__=='__main__':unittest.main()
