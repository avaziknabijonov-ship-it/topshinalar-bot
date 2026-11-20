import tempfile,unittest
from pathlib import Path
from core import Store
from director import read
from miniapp import MiniService,initialize
from test_miniapp import TOKEN


class PriceTypes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)/'p.sqlite3'
        self.s=Store(str(path));self.s.configure([10],[20]);initialize(path);self.api=MiniService(self.s,TOKEN)
        with self.s.db:
            self.point=self.s.add('points',name='Main');self.client=self.s.client(20,'Mijoz','+998901234567','','')
            self.product=self.s.product(10,'Haida 315','100');self.s.move(20,self.product,self.point,10,'in','')
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def edit(self,key,**extra):
        return self.api.write(10,'price-type-'+key+'-0000000','editproduct',{'product':self.product,'name':'Haida 315','brand':'Haida','size':'315','price':'100',**extra})
    def test_wholesale_price_saved_cleared_and_exposed(self):
        self.edit('a',wholesale_price='85.50')
        item=[r for r in self.api.catalog(20)['items'] if r['id']==self.product][0]
        self.assertEqual((item['price'],item['wholesale_price']),(10000,8550))
        self.assertEqual(read(self.api,10,'products',{'start':'2000-01-01','end':'2100-01-01'})['items'][0]['wholesale_price'],8550)
        self.edit('b',wholesale_price='')
        item=[r for r in self.api.catalog(20)['items'] if r['id']==self.product][0]
        self.assertIsNone(item['wholesale_price'])
    def test_wholesale_price_director_only_and_valid(self):
        with self.assertRaises(Exception):
            self.api.write(20,'price-type-c-0000000','editproduct',{'product':self.product,'name':'X','price':'1','wholesale_price':'1'})
        with self.assertRaises(ValueError):self.edit('d',wholesale_price='-5')
    def test_client_category(self):
        c=self.api.write(10,'price-type-e-0000000','director_client_save',{'client':self.client,'name':'Mijoz','phone':'+998901234567','address':'','note':'','owner':20,'category':'wholesale','revision':read(self.api,10,'clients',{'start':'2000-01-01','end':'2100-01-01'})['items'][0]['revision']})
        rows=read(self.api,10,'clients',{'start':'2000-01-01','end':'2100-01-01'})['items']
        self.assertEqual(rows[0]['category'],'wholesale')
        self.assertEqual(self.api.write(10,'price-type-f-0000000','director_client_save',{'name':'Yangi','phone':'','owner':20,'category':'retail'})['ok'],True)
        with self.assertRaises(ValueError):self.api.write(10,'price-type-g-0000000','director_client_save',{'name':'Bad','phone':'','owner':20,'category':'vip'})


if __name__=='__main__':unittest.main()
