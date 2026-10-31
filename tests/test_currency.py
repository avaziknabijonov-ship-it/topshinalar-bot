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

    def test_pdf_shows_unit_price_without_quantity_or_totals(self):
        from unittest.mock import patch
        from reportlab.platypus import Table
        from core import fmt
        ref=self.quote()
        for lang in ('uz','ru'):
            with self.s.db:self.s.db.execute('UPDATE quotes SET lang=? WHERE id=?',(lang,ref))
            with patch('quotation.SimpleDocTemplate.build') as build:quotation_pdf(self.s,20,ref)
            story=build.call_args.args[0]
            table=next(x for x in story if isinstance(x,Table) and len(x._colWidths)==3)
            cells=[[c.getPlainText() if hasattr(c,'getPlainText') else '' for c in row] for row in table._cellvalues]
            self.assertEqual(len(cells[0]),3)
            self.assertEqual(cells[0][-1],'1 dona narxi' if lang=='uz' else 'Цена за 1 шт.')
            self.assertEqual(cells[1][-1],fmt(15795817))
            text=' '.join(c for row in cells for c in row)+' '.join(x.getPlainText() for x in story if hasattr(x,'getPlainText'))
            self.assertNotIn(fmt(47387451),text)
            for label in ('Итого:','Jami:','Сумма','Шт.'):
                self.assertNotIn(label,text)
        self.assertEqual(self.s.one('quotes',ref)['total'],47387451)

    def test_quote_product_photo_is_larger_and_preserves_proportions(self):
        from quotation import product_image
        picture=product_image('catalog:haida-hd183-b6119c.jpg')
        self.assertIsNotNone(picture)
        self.assertGreater(picture.drawHeight,62)
        self.assertLessEqual(picture.drawHeight,120)
        self.assertLessEqual(picture.drawWidth,100)
        self.assertAlmostEqual(picture.drawWidth/picture.drawHeight,picture.imageWidth/picture.imageHeight)

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

    def test_four_large_product_photos_and_terms_fit_one_page_in_both_languages(self):
        from unittest.mock import patch
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.platypus import SimpleDocTemplate
        photos=['catalog:haida-hd183-b6119c.jpg','catalog:haida-hd776-2ecaf7.jpg','catalog:haida-hd168-948d35.jpg','catalog:haida-hd269-48619e.jpg']
        with self.s.db:
            products=[]
            for index,photo in enumerate(photos):
                product=self.s.product(10,'Haida HD'+str(index)+' 315/80R22.5 22PR','380')
                self.s.db.execute('UPDATE products SET photo=? WHERE id=?',(photo,product));products.append(product)
        ref=self.service.write(20,'four-photo-layout','quote',{'client':self.client,'items':[{'product':product,'qty':1,'price':'380'} for product in products],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000'})['id']
        original_build=SimpleDocTemplate.build
        for lang in ('uz','ru'):
            pages=[]
            class PageCounter(Canvas):
                def showPage(self):pages.append(self.getPageNumber());super().showPage()
            def build(doc,story,**kwargs):return original_build(doc,story,canvasmaker=PageCounter,**kwargs)
            with self.s.db:self.s.db.execute('UPDATE quotes SET lang=? WHERE id=?',(lang,ref))
            with patch('quotation.SimpleDocTemplate.build',new=build):
                self.assertTrue(quotation_pdf(self.s,20,ref).startswith(b'%PDF'))
            self.assertEqual(pages,[1],lang)

    def test_contact_qr_has_approved_website_phone_and_address(self):
        from quotation import company_contact_payload, company_contact_qr, COMPANY_ADDRESS
        from reportlab.graphics.shapes import Drawing
        payload=company_contact_payload()
        self.assertTrue(payload.startswith('BEGIN:VCARD\r\nVERSION:3.0'))
        self.assertIn('URL:https://topshinalar.uz',payload)
        self.assertIn('TEL;TYPE=WORK,VOICE:+998974788606',payload)
        self.assertIn("54A",payload)
        self.assertIn("Tariq-Teshar",payload)
        self.assertTrue(payload.endswith('END:VCARD'))
        self.assertIsInstance(company_contact_qr(),Drawing)

    def test_qr_opens_company_page_and_company_details_are_scan_only(self):
        from unittest.mock import patch
        from quotation import company_contact_payload, COMPANY_PHONE, COMPANY_ADDRESS
        with patch.dict('os.environ',{'PUBLIC_APP_URL':'https://bot.example.uz/'}):
            self.assertEqual(company_contact_payload(),'https://bot.example.uz/company')
        from reportlab.platypus import Table
        ref=self.service.write(20,'qr-scan-only-0001','quote',{'client':self.client,'items':[{'product':self.product,'qty':1,'price':'380'}],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000'})['id']
        with patch('quotation.SimpleDocTemplate.build') as build:quotation_pdf(self.s,20,ref)
        def visible_text(items):
            parts=[]
            for item in items:
                if isinstance(item,Table):
                    for row in item._cellvalues:parts.extend(visible_text(row))
                elif hasattr(item,'getPlainText'):parts.append(item.getPlainText())
            return parts
        text=' '.join(visible_text(build.call_args.args[0]))
        for hidden in (COMPANY_ADDRESS,'+998 97 478 86 06','https://topshinalar.uz'):
            self.assertNotIn(hidden,text)
        self.assertIn('Aloqa uchun:',text)

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
            self.assertIn('Yetkazib berish kelishilgan holda' if lang=='uz' else 'Доставка по согласованию',text)
            self.assertEqual(sum(isinstance(x,PageBreak) for x in story),0)
            self.assertEqual(sum(isinstance(x,Image) for x in story),0)
            self.assertEqual(len(next(x for x in story if isinstance(x,Table) and len(x._colWidths)==3)._colWidths),3)

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
