import tempfile,unittest
from pathlib import Path
from core import Store
from director import read
from miniapp import MiniService,initialize
from test_miniapp import TOKEN


class UnlinkedPayments(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)/'u.sqlite3'
        self.s=Store(str(path));self.s.configure([10],[20]);initialize(path);self.api=MiniService(self.s,TOKEN)
        with self.s.db:
            point=self.s.add('points',name='Main');client=self.s.client(20,'Mijoz','+998901234567','','')
            product=self.s.product(10,'Haida 315','100');self.s.move(20,product,point,10,'in','')
        self.api.write(20,'unlinked-test-sale-0001','sell',{'client':client,'point':point,'items':[{'product':product,'qty':1,'price':'100'}],'paid':'100','payment':'naqd'})
        self.api.write(10,'unlinked-test-recv-0001','manager_received',{'manager':20,'amount':'25','currency':'USD','date':self.s.now()[:10] if hasattr(self.s,'now') else __import__('core').now()[:10],'note':'Oldindan to‘lov'})
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def rows(self,**q):
        d=__import__('core').now()[:10]
        return read(self.api,10,'payments',{'start':d,'end':d,**q})['items']
    def test_marked_and_filterable(self):
        every=self.rows();self.assertEqual(sorted(bool(r.get('unlinked')) for r in every),[False,True])
        self.assertEqual([r['amount'] for r in self.rows(link='unlinked')],[2500])
        self.assertEqual([r['amount'] for r in self.rows(link='linked')],[10000])
        self.assertEqual(self.rows(client='1'),[r for r in every if not r.get('unlinked')])


if __name__=='__main__':unittest.main()
