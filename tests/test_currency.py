"""USD amounts and immutable UZS quotation snapshots."""
import unittest
import sqlite3
import tempfile
from pathlib import Path
from decimal import Decimal
import test_miniapp as fixtures
from core import Store, SCHEMA, exchange_rate, now
from quotation import quotation_pdf

class CurrencyTests(unittest.TestCase):
    setUp=fixtures.MiniAppTests.setUp
    tearDown=fixtures.MiniAppTests.tearDown

    def quote(self,rate='12800.50',price='12.34',qty=3,key='currency-quote-0001'):
        return self.service.write(20,key,'quote',{'client':self.client,'items':[{'product':self.product,'qty':qty,'price':price}],'payment':'naqd','fulfillment':'pickup','exchange_rate':rate})['id']

    def test_quote_converts_usd_to_uzs_and_does_not_sell(self):
        ref=self.quote()
        q=self.s.one('quotes',ref)
        self.assertEqual(q['currency'],'UZS')
        self.assertEqual(q['exchange_rate'],'12800.50')
        self.assertEqual(q['source_total_usd'],3702)
        self.assertEqual(q['total'],47387451)
        self.assertEqual(self.s.rows('SELECT price FROM quote_items')[0]['price'],15795817)
        self.assertEqual(self.s.stock(20)[0]['qty'],10)
        self.assertEqual(self.s.rows('SELECT * FROM sales'),[])
        self.assertEqual(self.s.rows('SELECT * FROM payments'),[])
        self.assertEqual(self.s.debts(20),[])
        before=quotation_pdf(self.s,20,ref)
        self.assertTrue(before.startswith(b'%PDF'))
        with self.s.db:self.s.edit_product(10,self.product,'Changed','','','99')
        self.quote(rate='13000',key='currency-quote-0002')
        self.assertEqual(self.s.one('quotes',ref)['total'],47387451)
        self.assertEqual(self.s.one('quotes',ref)['exchange_rate'],'12800.50')

    def test_manual_rate_required_and_validated_without_writes(self):
        for i,rate in enumerate([None,'',0,-1,'NaN','Infinity','0.001','1000001','abc']):
            with self.subTest(rate=rate),self.assertRaisesRegex(ValueError,'exchange_rate'):
                self.quote(rate=rate,key=f'currency-invalid-{i:04}')
        self.assertEqual(self.s.rows('SELECT * FROM quotes'),[])
        self.assertEqual(exchange_rate('12 800,50'),Decimal('12800.50'))

    def test_usd_sale_payment_and_legacy_debt_stay_separate(self):
        self.service.write(20,'currency-sale-0001','sell',self.sale_data)
        with self.s.db:
            old=self.s.add('sales',client=self.client,actor=20,point=self.point,total=500000,paid=0,payment='naqd',created=now(),currency='UZS')
            self.s.payment(20,old,'100','naqd')
        self.assertEqual(self.s.one('sales',1)['currency'],'USD')
        self.assertEqual(self.s.rows('SELECT currency FROM payments WHERE sale=?',(old,))[0]['currency'],'UZS')
        summary=self.service.dashboard(20)
        self.assertEqual(summary['total'],500000000)
        self.assertEqual(summary['received'],100000000)
        self.assertGreater(summary['legacy_count'],0)

class QuotationPresentationTests(unittest.TestCase):
    setUp=fixtures.MiniAppTests.setUp
    tearDown=fixtures.MiniAppTests.tearDown

    def test_selected_photo_snapshot_and_missing_photo(self):
        from quotation import product_image
        reference='catalog:haida-hd183-b6119c.jpg'
        with self.s.db:self.s.db.execute('UPDATE products SET photo=? WHERE id=?',(reference,self.product))
        ref=self.service.write(20,'photo-snapshot-0001','quote',{'client':self.client,'items':[{'product':self.product,'qty':1,'price':'380'}],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000'})['id']
        with self.s.db:self.s.db.execute('UPDATE products SET photo=NULL WHERE id=?',(self.product,))
        saved=self.s.rows('SELECT photo FROM quote_items WHERE quote=?',(ref,))[0]['photo']
        self.assertEqual(saved,reference)
        self.assertIsNotNone(product_image(saved))
        self.assertIsNone(product_image('catalog:missing-model.jpg'))
        self.assertIsNone(product_image(''))

    def test_pdf_presentation_in_both_languages(self):
        from unittest.mock import patch
        from reportlab.platypus import Image, PageBreak, Table
        ref=self.service.write(20,'presentation-0001','quote',{'client':self.client,'items':[{'product':self.product,'qty':1,'price':'380'}],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000'})['id']
        for lang in ('uz','ru'):
            with self.s.db:self.s.db.execute('UPDATE quotes SET lang=? WHERE id=?',(lang,ref))
            with patch('quotation.SimpleDocTemplate.build') as build:quotation_pdf(self.s,20,ref)
            story=build.call_args.args[0]
            text=' '.join(x.getPlainText() for x in story if hasattr(x,'getPlainText'))
            for forbidden in ('Customer','+998901234567','USD','UZS','Kurs:','Курс:','Mijoz:','Клиент:'):
                self.assertNotIn(forbidden,text)
            self.assertIn('Istalgan to‘lov usuli' if lang=='uz' else 'Любая форма оплаты',text)
            self.assertIn('Kelishuv asosida' if lang=='uz' else 'По договорённости',text)
            self.assertEqual(sum(isinstance(x,PageBreak) for x in story),2)
            self.assertEqual(sum(isinstance(x,Image) for x in story),3)
            self.assertEqual(len(next(x for x in story if isinstance(x,Table))._colWidths),5)

class CurrencyMigrationTests(unittest.TestCase):
    def test_old_amount_and_quote_retained_prices_require_usd_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'old.sqlite3'
            db=sqlite3.connect(path);db.executescript(SCHEMA)
            db.execute("INSERT INTO products(name,price) VALUES('Old tyre',250000000)")
            db.execute("INSERT INTO users(id,role,name) VALUES(20,'director','Old user')")
            db.execute("INSERT INTO clients(id,name,phone,address,note,owner,created) VALUES(1,'Old client','','','',20,'2026-10-16')")
            db.execute("INSERT INTO quotes(client,actor,total,terms,lang,created) VALUES(1,20,123400,'old','uz','2026-10-16')")
            db.execute("INSERT INTO sessions(user_id,data) VALUES(20,'{\"cmd\":\"sell\"}')")
            db.commit();db.close()
            s=Store(str(path))
            try:
                self.assertEqual(s.rows('SELECT * FROM sessions'),[])
                self.assertEqual(s.one('products',1)['price'],250000000)
                self.assertEqual(s.one('products',1)['currency'],'UZS')
                self.assertEqual(s.one('products',1)['price_pending'],1)
                self.assertEqual(s.one('quotes',1)['total'],123400)
                self.assertEqual(s.one('quotes',1)['currency'],'UZS')
                self.assertEqual(s.one('quotes',1)['exchange_rate'],'')
            finally:s.db.close()
