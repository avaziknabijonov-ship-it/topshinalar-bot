import tempfile,unittest
from pathlib import Path
from core import Store,now
from director import read
from miniapp import MiniService,initialize
from test_miniapp import TOKEN


class Cashbox(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)/'c.sqlite3'
        self.s=Store(str(path));self.s.configure([10],[20]);initialize(path);self.api=MiniService(self.s,TOKEN)
        self.today=now()[:10]
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def rec(self,key,kind,amount,uid=10):
        return self.api.write(uid,'cashbox-test-'+key+'-0000','manager_record',{'manager':20,'kind':kind,'amount':amount,'currency':'USD','note':'x','date':self.today})
    def test_expense_cannot_exceed_manager_money(self):
        self.rec('fund1','fund','100')
        with self.assertRaises(ValueError):self.rec('exp1','expense','100.01')
        self.rec('exp2','expense','60')
        with self.assertRaises(ValueError):self.rec('exp3','expense','40.01')
        self.rec('exp4','expense','40')
    def test_cashbox_totals_and_rates(self):
        self.rec('fund2','fund','100');self.rec('exp5','expense','30')
        self.api.write(10,'cashbox-test-rate1-0000','exchange_rate',{'date':self.today,'rate':'12800'})
        self.api.write(10,'cashbox-test-rate2-0000','exchange_rate',{'date':self.today,'rate':'12850'})
        d=read(self.api,10,'cashbox',{'start':self.today,'end':self.today})
        usd=d['totals'][0];self.assertEqual((usd['given'],usd['expenses'],usd['balance']),(10000,3000,7000))
        self.assertEqual([r['rate'] for r in d['rates']],['12850'])
        self.assertEqual(d['current_rate']['rate'],'12850')
    def test_rate_rules(self):
        with self.assertRaises(Exception):self.api.write(20,'cashbox-test-rate3-0000','exchange_rate',{'date':self.today,'rate':'12800'})
        with self.assertRaises(ValueError):self.api.write(10,'cashbox-test-rate4-0000','exchange_rate',{'date':self.today,'rate':'-5'})


if __name__=='__main__':unittest.main()
