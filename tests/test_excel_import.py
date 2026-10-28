"""Real XLSX fixtures built from minimal OOXML; no production credentials."""
import base64
import io
import json
import zipfile
from xml.sax.saxutils import escape
import unittest
import test_staff as fixtures
from excel_import import InventoryExcel,ExcelError


def xlsx(rows):
    cells=[]
    for n,row in enumerate(rows,1):
        values=[]
        for col,v in enumerate(row):
            ref=chr(65+col)+str(n)
            if v is None:continue
            if isinstance(v,(int,float)):cell=f'<c r="{ref}"><v>{v}</v></c>'
            elif str(v).startswith('='):cell=f'<c r="{ref}"><f>{escape(str(v)[1:])}</f><v>1</v></c>'
            else:cell=f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
            values.append(cell)
        cells.append(f'<row r="{n}">'+''.join(values)+'</row>')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ombor" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(cells)+'</sheetData></worksheet>')
    return base64.b64encode(buf.getvalue()).decode()

class ExcelTests(unittest.TestCase):
    setUp=fixtures.StaffTests.setUp
    tearDown=fixtures.StaffTests.tearDown
    def fixture(self,rows):
        with self.s.db:
            point=self.s.add('points',name='Main')
        return {'file':xlsx(rows),'point':point}
    def preview(self,data):return self.service.write(10,'excel-preview-0000-'+str(len(self.s.rows('SELECT * FROM mini_requests'))),'excel_preview',{**data,'mode':'income'})['id']
    def commit(self,data,preview,key='excel-import-0001'):
        return self.service.write(10,key,'excel_import',{**data,'mode':'income','sheet':preview['sheet'],'fingerprint':preview['fingerprint']})

    def test_preview_no_writes_new_products_atomic_and_replay(self):
        d=self.fixture([['Nomi','Brend','Razmer','Narx','Qoldiq'],['Haida HD','Haida','315/80','600 000',4]])
        p=self.preview(d);self.assertEqual(p['new_count'],1)
        self.assertEqual(self.s.rows('SELECT * FROM products'),[])
        a=self.commit(d,p);b=self.commit(d,p)
        self.assertEqual(a,b)
        self.assertEqual(self.s.rows('SELECT qty FROM stock'),[{'qty':4}])
        self.assertEqual(self.s.rows('SELECT price FROM products'),[{'price':60000000}])
        self.assertEqual(len(self.s.rows('SELECT * FROM movements')),1)

    def test_existing_receipt_adds_stock_updates_price_preserves_other_warehouse_and_rejects_stale(self):
        d=self.fixture([['ID','Цена','Остаток'],[1,200,3]])
        with self.s.db:
            ref=self.s.product(10,'Tyre','100')
            self.s.move(10,ref,d['point'],10,'in','')
            other=self.s.add('points',name='Other');self.s.move(10,ref,other,7,'in','')
        p=self.preview(d)
        with self.s.db:self.s.move(10,ref,d['point'],1,'in','')
        with self.assertRaises(ExcelError):self.commit(d,p)
        self.assertEqual(self.s.one('products',ref)['price'],10000)
        p=self.preview(d);self.commit(d,p)
        self.assertEqual(self.s.rows('SELECT point,qty FROM stock ORDER BY point'),[{'point':d['point'],'qty':14},{'point':other,'qty':7}])
        self.assertEqual(self.s.rows("SELECT qty FROM movements WHERE kind='excel_income'"),[{'qty':3}])

    def test_invalid_row_duplicate_formula_or_ambiguous_does_not_partially_write(self):
        bads=[
            [['Name','Price','Qty'],['Good',100,2],['Bad',-1,3]],
            [['Name','Price','Qty'],['Same',1,2],['Same',2,3]],
            [['Name','Price','Qty'],['Formula','=10+1',2]],
            [['Name','Price','Qty'],['Fraction',10,1.5]],
        ]
        for i,rows in enumerate(bads):
            d={'file':xlsx(rows),'point':1}
            if i==0:
                with self.s.db:self.s.add('points',id=1,name='Main')
            with self.assertRaises(ExcelError):self.preview(d)
            self.assertEqual(self.s.rows('SELECT * FROM products'),[])
        with self.s.db:
            self.s.product(10,'Same','10');self.s.product(10,'Same','20')
        with self.assertRaises(ExcelError):self.preview({'file':xlsx([['Name','Price','Qty'],['Same',10,2]]),'point':1})

    def test_employee_denied_and_zero_is_explicit_known_stock(self):
        d=self.fixture([['Name','Price','Qty'],['Zero',0,0]])
        for cmd in ['excel_preview','excel_import']:
            with self.assertRaises(PermissionError):self.service.write(20,'denied-'+cmd,cmd,d)
        p=self.preview(d);self.commit(d,p)
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],0)
        self.assertEqual(self.s.rows('SELECT price_pending FROM products')[0]['price_pending'],0)
        with self.assertRaises(ExcelError):self.preview({'point':d['point'],'file':'not an excel file'})

    def test_new_product_card_then_receipt_adds_quantity_once(self):
        with self.s.db:point=self.s.add('points',name='Main')
        ref=self.service.write(10,'new-product-card-01','product',{'name':'New tyre','brand':'Haida','size':'315/80','price':'600000'})['id']
        self.assertEqual(self.s.rows('SELECT * FROM stock'),[])
        data={'product':ref,'point':point,'qty':4,'note':'Arrival'}
        first=self.service.write(10,'single-receipt-01','income',data)
        self.assertEqual(first,self.service.write(10,'single-receipt-01','income',data))
        self.assertEqual(self.s.rows('SELECT qty FROM stock'),[{'qty':4}])

    def test_twenty_plus_ten_and_old_sale_price_unchanged(self):
        d=self.fixture([['ID','Narx','Kelgan dona'],[1,600000,10]])
        with self.s.db:
            ref=self.s.product(10,'Tyre','500000')
            self.s.move(10,ref,d['point'],21,'in','')
            client=self.s.client(20,'Client','+998901234567','','')
            sale=self.s.order(20,client,[{'product':ref,'qty':1,'price':'500000'}],point=d['point'],paid='500000',payment='naqd')
        p=self.preview(d)
        self.assertEqual(p['rows'][0]['old_qty'],20)
        self.assertEqual(p['rows'][0]['new_qty'],30)
        self.commit(d,p)
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],30)
        self.assertEqual(self.s.one('products',ref)['price'],60000000)
        self.assertEqual(self.s.rows('SELECT price FROM sale_items WHERE sale=?',(sale,))[0]['price'],50000000)
        with self.assertRaises(ExcelError):self.commit(d,p,key='repeat-different-key')
        self.assertEqual(self.s.rows('SELECT qty FROM stock')[0]['qty'],30)

    def test_old_snapshot_client_cannot_silently_add_stock(self):
        d=self.fixture([['Name','Price','Qty'],['Tyre',100,10]])
        with self.assertRaises(ExcelError):self.service.write(10,'old-client-preview1','excel_preview',d)
        self.assertEqual(self.s.rows('SELECT * FROM stock'),[])
