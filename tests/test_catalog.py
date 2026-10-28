import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from catalog import MANIFEST, import_catalog, local_photo
from core import Store
from bot import Bot, API
from miniapp import MiniService, initialize
from usability import matches_product


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.s=Store(str(Path(self.tmp.name)/'test.sqlite3'))
        self.s.configure([10],[20])
        initialize(Path(self.tmp.name)/'test.sqlite3')

    def tearDown(self):
        self.s.db.close();self.tmp.cleanup()

    def test_import_all_source_variants_without_prices_stock_or_duplicates(self):
        manifest=json.loads(MANIFEST.read_text())
        self.assertEqual(len(manifest),247)
        self.assertEqual(sum(len(r['sources']) for r in manifest),250)
        self.assertTrue(all(r['price'] is None and r['quantity'] is None for r in manifest))
        self.assertEqual(import_catalog(self.s),247)
        self.assertEqual(import_catalog(self.s),0)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),247)
        self.assertEqual(self.s.rows('SELECT * FROM stock'),[])
        self.assertTrue(all(r['price']==0 and r['price_pending']==1 for r in self.s.rows('SELECT * FROM products')))

    def test_reimport_preserves_manual_price_quantity_name_and_photo(self):
        import_catalog(self.s)
        with self.s.db:
            p=self.s.one('products',1)
            self.s.edit_product(10,1,'My edited name',p['brand'],p['size'],'2400000','telegram-photo')
            point=self.s.add('points',name='Main')
            self.s.move(20,1,point,17,'in','Opening stock')
        import_catalog(self.s)
        self.assertEqual(self.s.one('products',1)['price'],240000000)
        self.assertEqual(self.s.one('products',1)['price_pending'],0)
        self.assertEqual(self.s.one('products',1)['photo'],'telegram-photo')
        self.assertEqual(self.s.one('products',1)['name'],'My edited name')
        self.assertEqual(self.s.stock(20)[0]['qty'],17)

    def test_exact_existing_card_is_reused_without_commercial_changes(self):
        first=json.loads(MANIFEST.read_text())[0]
        with self.s.db:self.s.product(10,first['name'],'1234','my-photo')
        self.assertEqual(import_catalog(self.s),246)
        self.assertEqual(self.s.one('products',1)['price'],123400)
        self.assertEqual(self.s.one('products',1)['photo'],'my-photo')
        self.assertEqual(self.s.one('products',1)['price_pending'],0)

    def test_all_attached_images_exist_and_local_path_is_confined(self):
        manifest=json.loads(MANIFEST.read_text())
        for p in manifest:
            if p['photo']:
                data=local_photo(p['photo']).read_bytes()
                self.assertTrue(data.startswith(b'\xff\xd8'),p['name'])
        for path in ['catalog:../core.py','catalog:/etc/passwd','catalog:missing.jpg','catalog:photo.png']:
            with self.assertRaises(ValueError):local_photo(path)
        self.assertIsNone(local_photo('a-telegram-file-id'))

    def test_api_catalog_and_chat_distinguish_missing_price_and_stock(self):
        import_catalog(self.s)
        service=MiniService(self.s,'test-secret')
        first=service.catalog(20)['items'][0]
        self.assertTrue(first['price_pending']);self.assertTrue(first['stock_pending'])
        bot=Bot(self.s)
        bot.show_catalog(20,first['name'])
        payload=json.loads(self.s.rows('SELECT payload FROM outbox')[-1]['payload'])
        self.assertIn('Kiritilmagan',payload.get('caption',payload.get('text','')))
        self.assertIn('Qoldiq kiritilmagan',payload.get('caption',payload.get('text','')))
        with self.s.db:
            point=self.s.add('points',name='Main')
            self.s.move(20,first['id'],point,5,'in','Opening')
        self.assertFalse(service.catalog(20)['items'][0]['stock_pending'])

    def test_local_image_is_served_without_external_lookup_and_chat_uploads_bytes(self):
        import_catalog(self.s)
        p=self.s.rows('SELECT * FROM products WHERE photo IS NOT NULL')[0]
        service=MiniService(self.s,'test-secret')
        with patch('miniapp.urllib.request.urlopen',side_effect=AssertionError('No remote request')):
            self.assertEqual(service.photo(20,p['id']),local_photo(p['photo']).read_bytes())
        bot=Bot(self.s)
        with self.s.db:bot.queue(20,'Caption',photo=p['photo'],keyboard={'inline_keyboard':[]})
        with patch.object(API,'photo') as upload:
            bot.drain(API('fake-token'))
            self.assertEqual(upload.call_count,1)
            self.assertTrue(upload.call_args.args[1].startswith(b'\xff\xd8'))

    def test_all_metric_imperial_and_bias_sizes_are_searchable(self):
        for query,row in [('12,00 R20',{'name':'Haida HD183 12.00R20 22PR'}),('13 R22.5',{'name':'Haida HD183 13R22.5 20PR'}),('20,5-25',{'name':'OTRSTAR HT236 20.5-25 24PR'}),('HAIDA 315/80',{'name':'Haida HD776 315/80R22.5'})]:
            self.assertTrue(matches_product(query,row),query)
        self.assertFalse(matches_product('12.00R24',{'name':'Haida HD183 12.00R20'}))

    def test_rejects_supplier_price_and_duplicate_sku_before_any_insert(self):
        manifest=json.loads(MANIFEST.read_text())
        for rows in [[manifest[0],manifest[0]],[{**manifest[0],'price':130}]]:
            path=Path(self.tmp.name)/'bad.json';path.write_text(json.dumps(rows))
            with self.assertRaises(ValueError):import_catalog(self.s,path)
            self.assertEqual(self.s.rows('SELECT * FROM products'),[])


    def test_director_can_set_known_zero_once_and_reimport_preserves_it(self):
        import_catalog(self.s)
        with self.s.db:point=self.s.add('points',name='Main')
        service=MiniService(self.s,'test-secret')
        service.write(10,'initial-stock-000001','opening_stock',{'product':1,'point':point,'qty':0})
        self.assertFalse(service.catalog(20)['items'][0]['stock_pending'])
        self.assertEqual(self.s.stock(20)[0]['qty'],0)
        with self.assertRaises(ValueError):service.write(10,'initial-stock-000002','opening_stock',{'product':1,'point':point,'qty':25})
        import_catalog(self.s)
        self.assertEqual(self.s.stock(20)[0]['qty'],0)

    def test_employee_and_fractional_initial_stock_are_rejected(self):
        import_catalog(self.s)
        with self.s.db:point=self.s.add('points',name='Main')
        service=MiniService(self.s,'test-secret')
        with self.assertRaises(PermissionError):service.write(20,'initial-stock-000001','opening_stock',{'product':1,'point':point,'qty':0})
        for qty in [True,1.5,'1.5',-1,1000001]:
            with self.assertRaises(ValueError):service.write(10,'initial-stock-000003','opening_stock',{'product':1,'point':point,'qty':qty})
        self.assertEqual(self.s.rows('SELECT * FROM stock'),[])

    def test_initial_stock_retry_is_idempotent_and_audited(self):
        import_catalog(self.s)
        with self.s.db:point=self.s.add('points',name='Main')
        service=MiniService(self.s,'test-secret')
        data={'product':1,'point':point,'qty':25}
        result=service.write(10,'initial-stock-000001','opening_stock',data)
        self.assertEqual(result,service.write(10,'initial-stock-000001','opening_stock',data))
        self.assertEqual(self.s.stock(20)[0]['qty'],25)
        self.assertEqual(len(self.s.rows("SELECT * FROM movements WHERE kind='opening'")),1)
        self.assertEqual(len(self.s.rows("SELECT * FROM audit WHERE action='opening_stock'")),1)
