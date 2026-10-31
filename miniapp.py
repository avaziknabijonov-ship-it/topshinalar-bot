"""Telegram-authenticated Mini App sharing the employee bot's SQLite database."""
import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qsl,urlsplit
import urllib.request
from bot import Bot,API,ids
from core import Store,integer as core_integer,money,now,exchange_rate,normalize_contact_phone
from i18n import ERRORS
from usability import matches_product,size_parts
from catalog import import_catalog, local_photo
from staff import StaffAccess, permissions, require_command
from excel_import import InventoryExcel, ExcelError
import document_import

ROOT=Path(__file__).resolve().parent


class AuthError(Exception):pass


def integer(value):
    if type(value) is not int and not (isinstance(value,str) and re.fullmatch(r'\d+',value)):raise ValueError('quantity')
    return core_integer(value)


def telegram_id(value):
    if type(value) is not int and not (isinstance(value,str) and re.fullmatch(r'\d+',value)):raise ValueError('quantity')
    value=int(value)
    if not 0<value<=2**53:raise ValueError('quantity')
    return value


def authenticate(raw,token,clock=None,max_age=3600):
    if not raw or len(raw)>16000:raise AuthError()
    try:
        pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True)
        values=dict(pairs)
        if len(values)!=len(pairs):raise ValueError()
        received=values.pop('hash')
        secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
        check='\n'.join(f'{key}={value}' for key,value in sorted(values.items()))
        expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,received):raise ValueError()
        age=(clock if clock is not None else time.time())-int(values['auth_date'])
        if age < -30 or age>max_age:raise ValueError()
        user=json.loads(values['user'])
        if type(user.get('id')) is not int or user['id']<=0:raise ValueError()
        return user
    except (ValueError,KeyError,TypeError,AttributeError):raise AuthError() from None


def text(value,required=True,limit=1500):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):raise ValueError('text')
    return value.strip()


class MiniService:
    def __init__(self,store,token):self.s=store;self.b=Bot(store);self.token=token

    def identity(self,raw):
        signed=authenticate(raw,self.token);user=self.s.user(signed['id'])
        name=' '.join(str(signed.get(k,'')).strip() for k in ('first_name','last_name')).strip()
        if name:
            with self.s.db:self.s.db.execute('UPDATE users SET name=? WHERE id=?',(name[:150],user['id']))
            user['name']=name[:150]
        return user

    def catalog(self,uid,query='',point='',brand='',page=0):
        self.s.user(uid)
        groups={}
        for row in self.s.stock(uid):
            if not matches_product(query,row):continue
            if point and row['point_id']!=int(point):continue
            row_brand=row['brand'] or row['name'].split()[0]
            if brand and row_brand.casefold()!=brand.casefold():continue
            if row['id'] not in groups:
                parts=size_parts(row['name'])
                groups[row['id']]={'id':row['id'],'name':row['name'],'brand':row_brand,'size':row['size'] or ('/'.join(parts[:2])+(' R'+parts[2] if parts[2] else '') if parts else ''),'price':row['price'],'currency':row['currency'],'price_pending':bool(row['price_pending']),'stock_pending':bool(row['catalog_sku']),'photo':bool(row['photo']),'photo_reference':bool(row['photo'] and row['photo'].startswith('catalog:')),'points':[],'qty':0}
            if row['stock_set']:groups[row['id']]['stock_pending']=False
            if row['point_id'] is not None:
                groups[row['id']]['points'].append({'id':row['point_id'],'name':row['point'],'qty':row['qty'],'stock_pending':bool(row['catalog_sku'] and not row['stock_set'])})
                groups[row['id']]['qty']+=row['qty']
        items=list(groups.values());page=max(0,int(page))
        brands=sorted({p['brand'] or p['name'].split()[0] for p in self.s.rows('SELECT name,brand FROM products WHERE active=1')})
        return {'items':items[page*12:(page+1)*12],'total':len(items),'page':page,'brands':brands}

    def dashboard(self,uid,start=None,end=None):
        today=now()[:10];start=start or today;end=end or today
        data=self.s.report(uid,start,end);sales=[r for r in data['sales'] if r['status']=='active']
        debt=self.s.debts(uid)
        legacy_count=sum(r.get('currency')=='UZS' for rows in (sales,data['payments'],debt) for r in rows)
        sales=[r for r in sales if r['currency']=='USD']
        debt=[r for r in debt if r['currency']=='USD']
        data['payments']=[r for r in data['payments'] if r['currency']=='USD']
        data['refunds']=[r for r in data['refunds'] if r['currency']=='USD']
        return {'currency':'USD','legacy_count':legacy_count,'date':today,'start':start,'end':end,'sales':len(sales),'total':sum(r['total'] for r in sales),'received':sum(r['amount'] for r in data['payments']),'refunds':sum(r['amount'] for r in data['refunds']),'debt':sum(r['debt'] for r in debt),'overdue':sum(r['debt'] for r in debt if r['debt_due'] and r['debt_due']<today),'calls':len(data['calls']),'tasks':len(data['tasks']),'shift_open':bool(self.s.db.execute('SELECT 1 FROM shifts WHERE actor=? AND ended IS NULL',(uid,)).fetchone()),'lowstock':[r for r in self.b.low_rows() if r['qty']<=r['minimum']] if self.s.user(uid)['role']=='director' else []}

    def history(self,uid,kind):
        if kind not in {'sales','quotes','tasks'}:raise ValueError('table')
        scope='' if self.s.user(uid)['role']=='director' else ' WHERE r.actor=?'
        rows=self.s.rows(f'SELECT r.*,c.name client_name FROM {kind} r JOIN clients c ON c.id=r.client'+scope+' ORDER BY r.id DESC LIMIT 100',() if not scope else (uid,))
        if kind=='sales':
            for row in rows:row['items']=self.s.rows('SELECT name,qty,price FROM sale_items WHERE sale=?',(row['id'],))
        return rows

    def write(self,uid,key,cmd,data):
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',key or ''):raise ValueError('request_key')
        if not isinstance(data,dict):raise ValueError('text')
        digest=hashlib.sha256(json.dumps([cmd,data],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if cmd=='document_extract':
            self.s.director(uid)
            self.s.one('points',integer(data.get('point')))
            result=document_import.extract(data.get('file'))
            import difflib
            from excel_import import normalized
            products=self.s.rows('SELECT id,name FROM products WHERE active=1')
            for row in result['rows']:
                exact=[p for p in products if normalized(p['name'])==normalized(row['name'])]
                row['id']=exact[0]['id'] if len(exact)==1 else ''
                ranked=sorted(products,key=lambda p:difflib.SequenceMatcher(None,normalized(row['name']),normalized(p['name'])).ratio(),reverse=True)
                row['matches']=[p for p in ranked[:3] if difflib.SequenceMatcher(None,normalized(row['name']),normalized(p['name'])).ratio()>=0.45]
            return {'ok':True,'id':result}
        uploaded=None
        if cmd=='product_photo':
            self.s.director(uid);self.s.one('products',integer(data.get('product')))
            cached=self.s.db.execute('SELECT digest,result FROM mini_requests WHERE actor=? AND request_key=?',(uid,key)).fetchone()
            if cached:
                if cached['digest']!=digest:raise ValueError('request_changed')
                return json.loads(cached['result'])
            uploaded=self.upload_photo(uid,data)
        with self.s.db:
            self.s.db.execute('BEGIN IMMEDIATE');self.s.user(uid);require_command(self.s,uid,cmd)
            cached=self.s.db.execute('SELECT digest,result FROM mini_requests WHERE actor=? AND request_key=?',(uid,key)).fetchone()
            if cached:
                if cached['digest']!=digest:raise ValueError('request_changed')
                return json.loads(cached['result'])
            if cmd=='product_photo':
                self.s.director(uid);ref=integer(data['product'])
                self.s.db.execute('UPDATE products SET photo=? WHERE id=?',(uploaded,ref));self.s.log(uid,'product_photo',ref)
            else:ref=self.action(uid,cmd,data)
            result={'ok':True,'id':ref}
            self.s.add('mini_requests',actor=uid,request_key=key,digest=digest,result=json.dumps(result),created=now())
            return result

    def upload_photo(self,uid,data):
        try:photo=base64.b64decode(data.get('image',''),validate=True)
        except (ValueError,TypeError):raise ValueError('photo') from None
        if not photo or len(photo)>4*1024*1024 or not (photo.startswith(b'\xff\xd8') or photo.startswith(b'\x89PNG\r\n\x1a\n')):raise ValueError('photo')
        boundary='TopshinalarPhoto'+os.urandom(8).hex()
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{uid}\r\n--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="product.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+photo+f'\r\n--{boundary}--\r\n'.encode()
        request=urllib.request.Request('https://api.telegram.org/bot'+self.token+'/sendPhoto',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
        with urllib.request.urlopen(request,timeout=35) as response:result=json.load(response)
        if not result.get('ok') or not result.get('result',{}).get('photo'):raise ValueError('photo')
        return result['result']['photo'][-1]['file_id']

    def action(self,uid,cmd,d):
        require_command(self.s,uid,cmd)
        if cmd=='document_preview':return document_import.preview(self.s,uid,integer(d.get('point')),d.get('rows'))
        if cmd=='document_import':return document_import.apply(self.s,uid,integer(d.get('point')),d.get('rows'),d.get('fingerprint'),d.get('confirmed'))
        if cmd in {'excel_preview','excel_import'} and d.get('mode')!='income':raise ExcelError('Excel: Ilovani yopib /app orqali qayta oching. / Закройте приложение и откройте заново через /app.')
        if cmd=='excel_preview':return InventoryExcel(self.s).preview(uid,d.get('file'),integer(d.get('point')),text(d.get('sheet',''),False,100))
        if cmd=='excel_import':return InventoryExcel(self.s).apply(uid,d.get('file'),integer(d.get('point')),text(d.get('sheet',''),False,100),d.get('fingerprint'))
        if cmd=='staff_role':return StaffAccess(self.s).assign_role(uid,telegram_id(d.get('employee')),d.get('role'))
        if cmd=='pdf':
            ref=integer(d.get('ref'))
            self.b.execute(uid,'pdf',{'ref':ref})
            return ref
        if cmd=='report':
            self.b.make_report(uid,text(d.get('start','')),text(d.get('end','')),text(d.get('section','all')))
            return 'report_queued'
        if cmd=='staff_invite':
            self.s.director(uid)
            row=self.s.db.execute("SELECT value FROM meta WHERE key='bot_username'").fetchone()
            username=row['value'] if row else API(self.token).call('getMe',{}).get('username','')
            return StaffAccess(self.s).invite(uid,text(d.get('label',''),limit=100),username,d.get('role','employee'))
        if cmd=='staff_cancel_invite':return StaffAccess(self.s).cancel(uid,integer(d.get('invite')))
        if cmd=='staff_set':return StaffAccess(self.s).set_active(uid,telegram_id(d.get('employee')),d.get('active'))
        if cmd in {'sell','quote'}:
            client=integer(d.get('client'));items=d.get('items')
            if not isinstance(items,list) or not 1<=len(items)<=50:raise ValueError('items')
            clean=[{'product':integer(i.get('product')),'qty':integer(i.get('qty')),'price':str(i.get('price',''))} for i in items if isinstance(i,dict)]
            if len(clean)!=len(items):raise ValueError('items')
            payload={'client':client,'items':clean,'payment':text(d.get('payment',''))}
            if cmd=='sell':payload.update(point=integer(d.get('point')),paid=str(d.get('paid','0')))
            else:payload.update(fulfillment=text(d.get('fulfillment','')),exchange_rate=str(exchange_rate(d.get('exchange_rate'))))
            if cmd=='quote' and 'contact_phone' in d:payload['contact_phone']=normalize_contact_phone(d['contact_phone'])
            ref=self.b.execute(uid,cmd,payload)
            if cmd=='sell' and d.get('debt_due'):
                self.s.set_debt_due(uid,ref,text(d['debt_due']))
            return ref
        if cmd=='client':
            phone=re.sub(r'[\s()-]','',text(d.get('phone','')))
            if not re.fullmatch(r'\+?\d{9,15}',phone):raise ValueError('phone')
            return self.s.client(uid,text(d.get('name','')),phone,text(d.get('address',''),False),text(d.get('note',''),False))
        if cmd=='pay':return self.s.payment(uid,integer(d.get('sale')),str(d.get('amount','')),text(d.get('payment','')))
        if cmd=='debt_due':return self.s.set_debt_due(uid,integer(d.get('sale')),text(d.get('debt_due',''),False))
        if cmd=='cancel_sale':
            if type(d.get('expected_paid')) is not int:raise ValueError('sale_changed')
            return self.s.cancel_sale(uid,integer(d.get('sale')),text(d.get('reason','')),d.get('settlement') is True,d['expected_paid'])
        if cmd=='product':
            self.s.director(uid)
            ref=self.s.product(uid,text(d.get('name','')),str(d.get('price','')))
            self.s.db.execute('UPDATE products SET brand=?,size=? WHERE id=?',(text(d.get('brand',''),False,150),text(d.get('size',''),False,150),ref))
            if d.get('point'):
                self.s.opening_stock(uid,ref,integer(d['point']),d.get('qty','0'),'New product / Yangi mahsulot')
            elif str(d.get('qty','0')) not in {'','0'}:raise ValueError('no_points')
            return ref
        if cmd=='editproduct':
            return self.s.edit_product(uid,integer(d.get('product')),text(d.get('name','')),text(d.get('brand',''),False,150),text(d.get('size',''),False,150),str(d.get('price','')))
        if cmd=='minimum':return self.s.set_minimum(uid,integer(d.get('product')),integer(d.get('point')),d.get('minimum'))
        if cmd in {'income','return','writeoff'}:
            return self.s.move(uid,integer(d.get('product')),integer(d.get('point')),d.get('qty'),{'income':'in','return':'return','writeoff':'writeoff'}[cmd],text(d.get('note',''),False))
        if cmd=='opening_stock':
            return self.s.opening_stock(uid,integer(d.get('product')),integer(d.get('point')),d.get('qty'),text(d.get('note',''),False))
        if cmd=='point':
            self.s.director(uid);ref=self.s.add('points',name=text(d.get('name',''),limit=150));self.s.log(uid,'point',ref);return ref
        if cmd=='startwork':
            ref=self.s.start(uid);self.b.notify_shift(uid,'start');return ref
        if cmd=='endwork':return self.b.execute(uid,cmd,{'report':text(d.get('report',''))})
        if cmd=='call':return self.s.call(uid,integer(d.get('client')),text(d.get('result','')),text(d.get('note',''),False))
        if cmd=='task':return self.s.task(uid,integer(d.get('client')),telegram_id(d.get('assignee',uid)),text(d.get('due','')).replace('T',' '),text(d.get('note','')))
        if cmd=='done':self.s.complete_task(uid,integer(d.get('ref')));return int(d['ref'])
        if cmd=='fine':return self.s.fine(uid,telegram_id(d.get('employee')),str(d.get('amount','')),text(d.get('reason','')))
        if cmd=='delivery':
            return self.s.delivery(uid,integer(d.get('client')),integer(d['sale']) if d.get('sale') else None,text(d.get('driver','')),text(d.get('address','')),str(d.get('fee','')),str(d.get('paid','0')))
        if cmd=='delivery_status':self.s.delivery_status(uid,integer(d.get('ref')),text(d.get('status','')));return int(d['ref'])
        if cmd=='language':
            lang=d.get('lang')
            if lang not in {'uz','ru'}:raise ValueError('language')
            self.s.db.execute('UPDATE users SET lang=? WHERE id=?',(lang,uid));return uid
        raise ValueError('command')

    def photo(self,uid,product):
        self.s.user(uid);p=self.s.one('products',product)
        if not p['photo']:raise ValueError('photo')
        path=local_photo(p['photo'])
        if path:return path.read_bytes()
        info=API(self.token).call('getFile',{'file_id':p['photo']})
        path=info.get('file_path','')
        if not re.fullmatch(r'[A-Za-z0-9_./-]+',path) or '..' in path:raise ValueError('photo')
        with urllib.request.urlopen('https://api.telegram.org/file/bot'+self.token+'/'+path,timeout=20) as response:
            data=response.read(8*1024*1024+1)
        if len(data)>8*1024*1024:raise ValueError('photo')
        return data


def initialize(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS mini_requests(id INTEGER PRIMARY KEY,actor INTEGER NOT NULL,request_key TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(actor,request_key))')
        conn.commit()


class MiniServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,path,token,origin=''):
        self.db_path=str(path);self.bot_token=token;self.origin=origin.rstrip('/')
        initialize(path)
        super().__init__(address,MiniHandler)


class MiniHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def setup(self):super().setup();self.connection.settimeout(20)
    def send(self,status,payload,kind='application/json; charset=utf-8',filename=None):
        if not isinstance(payload,bytes):payload=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors https://web.telegram.org https://*.telegram.org; object-src 'none'; base-uri 'none'")
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)

    def do_GET(self):self.handle_request(False)
    def do_POST(self):self.handle_request(True)

    def handle_request(self,write):
        target=urlsplit(self.path);path=target.path
        static={'/mobile.js':('web/mobile.js','text/javascript; charset=utf-8'),'/company':('web/company.html','text/html; charset=utf-8'),'/company.css':('web/company.css','text/css; charset=utf-8'),'/company/registration.pdf':('assets/quotation-attachments/company-registration.pdf','application/pdf'),'/company/vat.pdf':('assets/quotation-attachments/vat-registration.pdf','application/pdf'),'/document-import.js':('web/document-import.js','text/javascript; charset=utf-8'),'/':('web/index.html','text/html; charset=utf-8'),'/app.js':('web/app.js','text/javascript; charset=utf-8'),'/app.css':('web/app.css','text/css; charset=utf-8'),'/logo.png':('assets/topshinalar-logo.png','image/png')}
        if not write and path in static:
            file,kind=static[path];self.send(200,(ROOT/file).read_bytes(),kind);return
        store=None;user=None
        try:
            origin=self.headers.get('Origin')
            if origin and self.server.origin and origin!=self.server.origin:raise AuthError()
            signed=authenticate(self.headers.get('X-Telegram-Init-Data',''),self.server.bot_token)
            store=Store(self.server.db_path);service=MiniService(store,self.server.bot_token)
            try:user=store.user(signed['id'])
            except (ValueError,PermissionError):raise AuthError() from None
            uid=user['id']
            name=' '.join(str(signed.get(k,'')).strip() for k in ('first_name','last_name')).strip()
            if name:
                with store.db:store.db.execute('UPDATE users SET name=? WHERE id=?',(name[:150],uid))
                user['name']=name[:150]
            if write:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=6*1024*1024:raise ValueError('text')
                body=json.loads(self.rfile.read(length))
                if path!='/api/action' or not isinstance(body,dict):raise ValueError('command')
                if body.get('cmd') in {'sell','quote','pay','product','editproduct','fine','delivery','excel_preview','excel_import','document_extract','document_preview','document_import'} and body.get('money_version')!=2:
                    raise ValueError('currency_reload')
                result=service.write(uid,self.headers.get('Idempotency-Key',''),body.get('cmd'),body.get('data'))
                self.send(200,result);return
            query=dict(parse_qsl(target.query));page=min(10000,max(0,int(query.get('page',0))))
            read_cmd={'/api/catalog':'catalog','/api/photo':'catalog','/api/clients':'clients','/api/debts':'debts','/api/sales':'sales','/api/quotes':'quotes','/api/tasks':'tasks','/api/report':'report'}
            require_command(store,uid,read_cmd.get(path,'pdf' if path.startswith('/api/quote/') else 'photo' if path.startswith('/api/photo/') else ''))
            if path=='/api/me':result={**{k:user[k] for k in ('id','name','role','lang')},'permissions':permissions(store,uid),'contact_phone':store.contact_phone(uid)}
            elif path=='/api/catalog':result=service.catalog(uid,query.get('q','')[:200],query.get('point',''),query.get('brand','')[:150],page)
            elif path=='/api/points':result=store.rows('SELECT id,name FROM points ORDER BY name,id')
            elif path=='/api/brands':
                result=[];seen=set()
                for row in store.rows("SELECT brand FROM products WHERE TRIM(brand)<>'' ORDER BY brand"):
                    brand=row['brand'].strip()
                    if brand.casefold() not in seen:result.append(brand);seen.add(brand.casefold())
            elif path=='/api/clients':
                q=' '.join(query.get('q','').casefold().split())[:200]
                rows=store.rows('SELECT id,name,phone,address,note FROM clients ORDER BY name,id')
                digits=re.sub(r'\D','',q)
                rows=[r for r in rows if q in ' '.join((r['name']+' '+r['phone']).casefold().split()) or (digits and re.fullmatch(r'[+\d\s()-]+',q) and digits in re.sub(r'\D','',r['phone']))]
                result={'items':rows[page*20:(page+1)*20],'total':len(rows)}
            elif path=='/api/debts':result=store.debts(uid,query.get('overdue')=='1')
            elif path=='/api/dashboard':
                result=service.dashboard(uid,query.get('start'),query.get('end'))
                allowed=permissions(store,uid)
                if 'sales' not in allowed:
                    for key in ('sales','total','received','refunds'):result[key]=0
                if 'debts' not in allowed:result['debt']=result['overdue']=0
                if 'calls' not in allowed:result['calls']=0
                if 'tasks' not in allowed:result['tasks']=0
            elif path=='/api/staff':
                store.director(uid);result=store.rows('SELECT id,name,role FROM users WHERE active=1 ORDER BY name,id')
            elif path=='/api/team':result=StaffAccess(store).team(uid)
            elif path in {'/api/sales','/api/quotes','/api/tasks'}:result=service.history(uid,path.split('/')[-1])
            elif path=='/api/report':
                from reports import workbook
                data=store.report(uid,query.get('start',now()[:10]),query.get('end',now()[:10]));data.update(store.inventory_report(uid))
                self.send(200,workbook(service.b.enrich(data),user['lang']),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','TOPSHINALAR-report.xlsx');return
            elif re.fullmatch(r'/api/quote/\d+\.pdf',path):
                from quotation import quotation_pdf
                ref=int(path.rsplit('/',1)[-1][:-4]);store.own(uid,store.one('quotes',ref))
                self.send(200,quotation_pdf(store,uid,ref),'application/pdf',f'TOPSHINALAR-KP-{ref}.pdf');return
            elif re.fullmatch(r'/api/photo/\d+',path):
                self.send(200,service.photo(uid,int(path.rsplit('/',1)[-1])),'image/jpeg');return
            else:self.send(404,{'error':'Not found'});return
            self.send(200,result)
        except (AuthError,PermissionError):self.send(403,{'error':'Telegram orqali kiring / Откройте через Telegram'})
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as exc:
            lang=user['lang'] if user else 'uz';message=ERRORS.get(str(exc),('Ma’lumotni tekshiring','Проверьте данные'))[lang=='ru']
            if isinstance(exc,ExcelError):message=str(exc)
            self.send(400,{'error':message})
        except Exception:
            logging.exception('Mini App request failed: %s %s','POST' if write else 'GET',path)
            self.send(503,{'error':'Vaqtincha ulanish yo‘q / Временно недоступно'})
        finally:
            if store:store.db.close()


def main():
    token=os.environ.get('BOT_TOKEN','')
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):raise SystemExit('BOT_TOKEN is required')
    path=os.path.abspath(os.environ.get('DB_PATH','data/topshinalar.sqlite3'))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    store=Store(path);store.configure(ids('DIRECTOR_IDS'),ids('EMPLOYEE_IDS'));import_catalog(store);store.db.close()
    origin=os.environ.get('PUBLIC_APP_URL','')
    if origin:
        parsed=urlsplit(origin)
        if parsed.scheme!='https' or not parsed.netloc or parsed.path not in {'','/'} or parsed.query or parsed.fragment:raise SystemExit('PUBLIC_APP_URL must be an HTTPS origin')
        origin=f'https://{parsed.netloc}'
    server=MiniServer((os.environ.get('MINIAPP_HOST','127.0.0.1'),int(os.environ.get('MINIAPP_PORT','8080'))),path,token,origin)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
