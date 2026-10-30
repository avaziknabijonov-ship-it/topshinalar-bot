"""Local PDF/photo OCR, followed by editable review and the existing atomic receipt import."""
import base64
import io
import re
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from openpyxl import Workbook
from excel_import import InventoryExcel, ExcelError, normalized

MAX_BYTES=4*1024*1024
MAX_PAGES=5
MAX_ROWS=100
LIMIT=threading.BoundedSemaphore(2)

def fail(uz,ru):raise ExcelError(uz+' / '+ru)

def run_command(args,deadline):
    seconds=min(15,deadline-time.monotonic())
    if seconds<=0:fail('Hujjatni qismlarga bo‘lib yuklang.','Загрузите документ частями.')
    try:
        with tempfile.TemporaryFile() as output:
            result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.DEVNULL,timeout=seconds,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
            if result.returncode:raise ValueError()
            output.seek(0);data=output.read(1024*1024+1)
            if len(data)>1024*1024:raise ValueError()
            return data.decode('utf-8',errors='replace')
    except FileNotFoundError:
        fail('Serverda PDF/OCR dasturi hali o‘rnatilmagan.','На сервере ещё не установлен модуль PDF/OCR.')
    except (subprocess.TimeoutExpired,ValueError):
        fail('Hujjatni o‘qib bo‘lmadi. Aniqroq rasm yoki kichikroq PDF yuklang.','Не удалось прочитать документ. Загрузите чёткое фото или PDF меньшего размера.')

def ocr(path,deadline):
    langs=run_command(['tesseract','--list-langs'],deadline).splitlines()
    available=[x for x in ('eng','rus','uzb') if x in langs]
    if not available:fail('OCR tillari o‘rnatilmagan.','Языки OCR не установлены.')
    return run_command(['tesseract',str(path),'stdout','-l','+'.join(available),'--psm','6','-c','preserve_interword_spaces=1'],deadline)

def parse_rows(text):
    """Only assign quantity/price automatically under recognized table headings."""
    columns=None;rows=[];unmatched=[]
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        cells=[c.strip() for c in re.split(r'\s*\|\s*|\t+| {2,}',line) if c.strip()]
        names=[normalized(c) for c in cells]
        header={}
        for i,name in enumerate(names):
            if name in {'name','nomi','nom','mahsulot','mahsulotnomi','tovar','tovarnomi','название','наименование','наименованиетовара','названиетовара','товар','модель','product','description'}:header['name']=i
            elif name in {'qty','quantity','количество','колво','дона','dona','kelgandona','soni','шт','штут','количествошт'}:header['qty']=i
            elif name in {'price','unitprice','priceusd','narx','narxi','narxusd','цена','ценаusd','ценаузс','ценаuzs','ценазашт','ценазаштusd','ценасндс','narxuzs'}:header['price']=i
        if {'name','qty','price'}<=header.keys():columns=header;continue
        # Never import invoice totals/tax/payment headings as a product.
        if re.match(r'^(итого|всего|ндс|jami|total|subtotal|to‘lov|оплата)\b',line,re.I):continue
        if columns and max(columns.values())<len(cells):
            row={key:cells[index] for key,index in columns.items()}
            if row['name'] and re.search(r'[A-Za-zА-Яа-я]',row['name']):
                rows.append({**row,'source':line})
                if len(rows)>MAX_ROWS:fail('Bir hujjatda 100 tagacha mahsulot.','Не более 100 товаров в документе.')
                continue
        unmatched.append(line)
    return rows,unmatched


def extract(encoded):
    if not isinstance(encoded,str) or len(encoded)>MAX_BYTES*4//3+8:fail('PDF yoki rasm 4 MB gacha bo‘lsin.','PDF или фото должны быть до 4 МБ.')
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):fail('Fayl noto‘g‘ri.','Некорректный файл.')
    if not raw or len(raw)>MAX_BYTES:fail('Fayl 4 MB gacha bo‘lsin.','Файл должен быть до 4 МБ.')
    if raw.startswith(b'%PDF-'):suffix='.pdf'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n'):suffix='.png'
    elif raw.startswith(b'\xff\xd8'):suffix='.jpg'
    else:fail('PDF, JPEG yoki PNG yuklang.','Загрузите PDF, JPEG или PNG.')
    if not LIMIT.acquire(blocking=False):fail('O‘qish band. Birozdan keyin urinib ko‘ring.','Распознавание занято. Повторите чуть позже.')
    try:
        deadline=time.monotonic()+40
        with tempfile.TemporaryDirectory(prefix='topshinalar-ocr-') as folder:
            source=Path(folder)/('source'+suffix);source.write_bytes(raw)
            texts=[]
            if suffix=='.pdf':
                info=run_command(['pdfinfo',str(source)],deadline)
                count=re.search(r'^Pages:\s*(\d+)',info,re.M)
                if not count or not 1<=int(count[1])<=MAX_PAGES:fail('PDF 1–5 sahifa bo‘lsin.','PDF должен содержать 1–5 страниц.')
                for page in range(1,int(count[1])+1):
                    page_text=run_command(['pdftotext','-layout','-f',str(page),'-l',str(page),str(source),'-'],deadline)
                    if not parse_rows(page_text)[0]:
                        prefix=Path(folder)/f'page-{page}'
                        run_command(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','2800','-singlefile','-png',str(source),str(prefix)],deadline)
                        page_text=ocr(prefix.with_suffix('.png'),deadline)
                    texts.append(page_text)
            else:
                # Verify decoded dimensions before passing a photo to OCR.
                from PIL import Image
                try:
                    with Image.open(source) as image:
                        if image.width*image.height>24_000_000:raise ValueError()
                        image.verify()
                except Exception:fail('Rasm o‘qilmadi yoki juda katta.','Фото не читается или слишком большое.')
                texts.append(ocr(source,deadline))
            text='\n'.join(texts)
            if len(text)>100000:fail('Hujjat juda uzun.','Документ слишком длинный.')
            rows,unmatched=parse_rows(text)
            return {'rows':rows,'text':text,'unmatched':unmatched[:100],'pages':len(texts),'review_required':True}
    finally:LIMIT.release()


def rows_file(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ROWS:fail('1–100 ta mahsulot kiriting.','Укажите от 1 до 100 товаров.')
    wb=Workbook();ws=wb.active;ws.append(['ID','Nomi','Narx USD','Kelgan dona'])
    for row in rows:
        if not isinstance(row,dict):raise ValueError('text')
        name=str(row.get('name','')).strip()
        if not name or len(name)>200:fail('Mahsulot nomini tekshiring.','Проверьте название товара.')
        # Cells are always plain strings; formulas are rejected by InventoryExcel.
        ref=row.get('id') or None
        ws.append([ref,name,str(row.get('price','')),str(row.get('qty',''))])
    out=io.BytesIO();wb.save(out)
    return base64.b64encode(out.getvalue()).decode()


def preview(store,uid,point,rows):
    return InventoryExcel(store).preview(uid,rows_file(rows),point)


def apply(store,uid,point,rows,fingerprint,confirmed):
    if confirmed is not True:fail('Qatorlar va USD narxlarni tekshirib tasdiqlang.','Проверьте строки и цены в USD и подтвердите.')
    return InventoryExcel(store).apply(uid,rows_file(rows),point,'',fingerprint)
