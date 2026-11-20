import tempfile,unittest
from pathlib import Path
from core import Store
from miniapp import MiniService,initialize
from receipt import sale_receipt_pdf
from test_miniapp import TOKEN


class Receipt(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)/'r.sqlite3'
        self.s=Store(str(path));self.s.configure([10],[20,21]);initialize(path);self.api=MiniService(self.s,TOKEN)
        with self.s.db:
            point=self.s.add('points',name='Main');client=self.s.client(20,'Mijoz','+998901234567','','')
            product=self.s.product(10,'Haida 315/80 R22.5','125.25');self.s.move(20,product,point,10,'in','')
            self.sale=self.s.order(20,client,[dict(product=product,qty=3,price='125.25')],point=point,paid='100',payment='naqd')
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def test_both_formats_and_languages(self):
        sizes={}
        for fmt in ('a4','80mm'):
            for lang in ('uz','ru'):
                pdf=sale_receipt_pdf(self.s,20,self.sale,fmt,lang)
                self.assertTrue(pdf.startswith(b'%PDF-'))
                sizes[fmt]=pdf.count(b'/Type /Page\n')+pdf.count(b'/Type /Page ')
        self.assertEqual(sizes['80mm'],1)
    def test_bad_format_and_ownership(self):
        with self.assertRaises(ValueError):sale_receipt_pdf(self.s,20,self.sale,'a3')
        with self.assertRaises(PermissionError):sale_receipt_pdf(self.s,21,self.sale,'a4')
        self.assertTrue(sale_receipt_pdf(self.s,10,self.sale,'a4').startswith(b'%PDF-'))
    def test_send_to_telegram_queues_document(self):
        before=self.s.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] if self.s.db.execute("SELECT 1 FROM sqlite_master WHERE name='outbox'").fetchone() else None
        self.api.write(20,'receipt-send-key-000001','receipt_send',{'sale':self.sale,'format':'80mm'})
        if before is not None:self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],before+1)
        with self.assertRaises(PermissionError):self.api.write(21,'receipt-send-key-000002','receipt_send',{'sale':self.sale,'format':'a4'})
        with self.assertRaises(ValueError):self.api.write(20,'receipt-send-key-000003','receipt_send',{'sale':self.sale,'format':'x'})


if __name__=='__main__':unittest.main()
