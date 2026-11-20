import tempfile,unittest
from pathlib import Path
from core import Store
from miniapp import MiniService,initialize
from test_miniapp import TOKEN


class MixedPayment(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)/'m.sqlite3'
        self.s=Store(str(path));self.s.configure([10],[20]);initialize(path);self.api=MiniService(self.s,TOKEN)
        with self.s.db:
            self.point=self.s.add('points',name='Main');self.client=self.s.client(20,'Mijoz','+998901234567','','')
            self.product=self.s.product(10,'Haida 315','100');self.s.move(20,self.product,self.point,10,'in','')
        self.data={'client':self.client,'point':self.point,'items':[{'product':self.product,'qty':2,'price':'100'}],'paid':'0','payment':'naqd'}
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def test_split_creates_payment_per_method(self):
        d=dict(self.data,splits=[{'method':'naqd','amount':'50'},{'method':'karta','amount':'70.50'}])
        ref=self.api.write(20,'mixed-pay-key-000001','sell',d)['id']
        sale=self.s.one('sales',ref)
        self.assertEqual(sale['paid'],12050)
        rows=self.s.rows('SELECT method,amount FROM payments WHERE sale=? ORDER BY id',(ref,))
        self.assertEqual([(r['method'],r['amount']) for r in rows],[('naqd',5000),('karta',7050)])
        self.assertEqual(sale['payment'],'karta')
    def test_split_cannot_exceed_total(self):
        d=dict(self.data,splits=[{'method':'naqd','amount':'150'},{'method':'karta','amount':'60'}])
        with self.assertRaises(ValueError):self.api.write(20,'mixed-pay-key-000002','sell',d)
    def test_bad_method_rejected_and_nothing_sold(self):
        d=dict(self.data,splits=[{'method':'bitcoin','amount':'10'}])
        with self.assertRaises(ValueError):self.api.write(20,'mixed-pay-key-000003','sell',d)
        self.assertEqual(self.s.rows('SELECT id FROM sales'),[])
    def test_plain_payment_unchanged(self):
        ref=self.api.write(20,'mixed-pay-key-000004','sell',dict(self.data,paid='40'))['id']
        self.assertEqual([r['amount'] for r in self.s.rows('SELECT amount FROM payments WHERE sale=?',(ref,))],[4000])


if __name__=='__main__':unittest.main()
