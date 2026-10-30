import base64
import io
import shutil
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import document_import as documents
import test_miniapp as fixtures

class DocumentReceiptTests(unittest.TestCase):
    setUp=fixtures.MiniAppTests.setUp
    tearDown=fixtures.MiniAppTests.tearDown

    def rows(self):
        return [{'id':self.product,'name':'Linglong 315/80 R22.5','qty':'3','price':'380.50'},
                {'name':'New Haida HD183','qty':'4','price':'350'}]

    def preview(self,rows=None):
        return self.service.write(10,'document-preview-001','document_preview',{'point':self.point,'rows':self.rows() if rows is None else rows})['id']

    def test_review_then_atomic_receipt_updates_price_and_adds_stock(self):
        old_price=self.s.one('products',self.product)['price']
        result=self.preview()
        self.assertEqual(self.s.stock(10)[0]['qty'],10)
        self.assertEqual(self.s.one('products',self.product)['price'],old_price)
        self.assertEqual(result['new_count'],1)
        data={'point':self.point,'rows':self.rows(),'fingerprint':result['fingerprint'],'confirmed':True}
        first=self.service.write(10,'document-import-001','document_import',data)
        second=self.service.write(10,'document-import-001','document_import',data)
        self.assertEqual(first,second)
        self.assertEqual(self.s.one('products',self.product)['price'],38050)
        self.assertEqual(self.s.stock(10)[0]['qty'],13)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),2)
        self.assertEqual(self.s.rows('SELECT qty FROM stock WHERE product<>?',(self.product,))[0]['qty'],4)

    def test_confirmation_and_stale_review_are_rejected_without_partial_writes(self):
        result=self.preview()
        data={'point':self.point,'rows':self.rows(),'fingerprint':result['fingerprint']}
        with self.assertRaises(ValueError):
            self.service.write(10,'document-unconfirmed','document_import',data)
        with self.s.db:self.s.move(20,self.product,self.point,1,'in','Other delivery')
        with self.assertRaises(ValueError):
            self.service.write(10,'document-stale-001','document_import',{**data,'confirmed':True})
        self.assertEqual(self.s.stock(10)[0]['qty'],11)
        self.assertEqual(len(self.s.rows('SELECT * FROM products')),1)

    def test_employees_cannot_extract_preview_or_apply_documents(self):
        for cmd in ('document_extract','document_preview','document_import'):
            with self.subTest(cmd=cmd),self.assertRaises(PermissionError):
                self.service.write(20,'document-denied-001',cmd,{'point':self.point,'file':'x','rows':self.rows()})

    def test_invalid_rows_do_not_change_inventory(self):
        for rows in ([],self.rows()+self.rows(),[{'name':'Bad','qty':'-1','price':'300'}],[{'name':'Bad','qty':'2','price':''}],[{'name':'=HYPERLINK(1)','qty':'2','price':'3'}]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.preview(rows)
        self.assertEqual(self.s.stock(10)[0]['qty'],10)

    def test_extraction_is_read_only_and_only_exact_match_is_auto_selected(self):
        extracted={'rows':[{'name':'Linglong 315/80 R22.5','qty':'2','price':'300'},{'name':'Linglong 315/80 R22.6','qty':'2','price':'310'}],'text':'source','unmatched':[]}
        with patch('document_import.extract',return_value=extracted):
            result=self.service.write(10,'document-read-0001','document_extract',{'point':self.point,'file':'data'})['id']
        self.assertEqual(result['rows'][0]['id'],self.product)
        self.assertEqual(result['rows'][1]['id'],'')
        self.assertTrue(result['rows'][1]['matches'])
        self.assertEqual(self.s.rows('SELECT * FROM mini_requests'),[])
        self.assertEqual(self.s.stock(10)[0]['qty'],10)


class DocumentParserTests(unittest.TestCase):
    def test_headers_control_column_order_and_totals_are_not_products(self):
        rows,other=documents.parse_rows('№  Название товара  Цена USD  Кол-во  Итого\n1  Haida HD183  380,50  3  1141,50\nИтого  1141,50')
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['name'],rows[0]['qty'],rows[0]['price']),('Haida HD183','3','380,50'))

    def test_no_guessed_quantity_or_price_without_headers(self):
        rows,other=documents.parse_rows('Haida HD183 12.00R20 22PR 3 380.00')
        self.assertEqual(rows,[])
        self.assertEqual(len(other),1)

    def test_invalid_file_types_and_limits(self):
        for data in ('invalid',base64.b64encode(b'not an invoice').decode(),'A'*(documents.MAX_BYTES*4//3+20)):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):documents.extract(data)

    @unittest.skipUnless(shutil.which('pdftotext') and shutil.which('pdfinfo'),'Poppler not installed')
    def test_real_text_pdf_extraction(self):
        out=io.BytesIO();pdf=canvas.Canvas(out)
        for y,name,qty,price in [(780,'Name','Qty','Price'),(740,'HAIDA HD183','3','380.50')]:
            pdf.drawString(40,y,name);pdf.drawString(350,y,qty);pdf.drawString(450,y,price)
        pdf.save()
        result=documents.extract(base64.b64encode(out.getvalue()).decode())
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['rows'][0]['qty'],'3')
        self.assertEqual(result['rows'][0]['price'],'380.50')

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract not installed')
    def test_real_photo_ocr(self):
        image=self.invoice_image();out=io.BytesIO();image.save(out,format='PNG')
        result=documents.extract(base64.b64encode(out.getvalue()).decode())
        self.assertEqual(len(result['rows']),1,result['text'])
        self.assertEqual(result['rows'][0]['qty'],'3')
        self.assertEqual(result['rows'][0]['price'],'380.50')

    @unittest.skipUnless(shutil.which('tesseract') and shutil.which('pdftoppm') and shutil.which('pdfinfo'),'OCR dependencies not installed')
    def test_real_scanned_pdf_ocr(self):
        image=self.invoice_image();out=io.BytesIO();pdf=canvas.Canvas(out)
        pdf.drawImage(ImageReader(image),30,500,width=540,height=160);pdf.save()
        result=documents.extract(base64.b64encode(out.getvalue()).decode())
        self.assertEqual(len(result['rows']),1,result['text'])
        self.assertEqual(result['rows'][0]['qty'],'3')

    @staticmethod
    def invoice_image():
        image=Image.new('RGB',(1500,420),'white')
        draw=ImageDraw.Draw(image);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',42)
        for y,name,qty,price in [(55,'Name','Qty','Price'),(180,'HAIDA HD183','3','380.50')]:
            draw.text((40,y),name,font=font,fill='black');draw.text((900,y),qty,font=font,fill='black');draw.text((1150,y),price,font=font,fill='black')
        return image
