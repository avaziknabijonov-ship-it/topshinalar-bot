import base64
import json
import logging
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime
from core import Store, now, TZ, integer, money, fmt, parse_item_lines
from i18n import tr, label, MENU, DIRECTOR_ONLY, ERRORS
from payments import normalize_payment, payment_label, payment_labels, normalize_fulfillment, fulfillment_label, fulfillment_labels
from storage import SingleInstance
from usability import Usability
from catalog import import_catalog, local_photo
from staff import require_command, permissions

# Each dialog collects fields, previews the result, then saves only after confirmation.
FORMS = {
'newclient': [('name','name'),('phone','phone'),('address','address'),('note','note')],
'newpoint': [('name','name')],
'newproduct': [('name','product_name'),('price','price'),('photo','photo')],
'income': [('product','product'),('point','point'),('qty','qty'),('note','note')],
'return': [('product','product'),('point','point'),('qty','qty'),('note','note')],
'writeoff': [('product','product'),('point','point'),('qty','qty'),('note','note')],
'sell': [('client','client'),('point','point'),('items','items'),('paid','paid'),('payment','payment')],
'pay': [('sale','sale'),('amount','amount'),('payment','payment')],
'quote': [('client','client'),('items','items'),('payment','payment'),('fulfillment','fulfillment'),('exchange_rate','exchange_rate')],
'quote_options': [('ref','ref'),('payment','payment'),('fulfillment','fulfillment')],
'call': [('client','client'),('result','result'),('note','note')],
'task': [('client','client'),('assignee','assignee'),('due','due'),('note','note')],
'done': [('ref','ref')],
'delivery': [('client','client'),('sale','optional_sale'),('driver','driver'),('address','address'),('fee','fee'),('paid','paid')],
'delivery_status': [('ref','ref'),('status','status')],
'fine': [('employee','employee'),('amount','amount'),('reason','reason')],
'endwork': [('report','shift_report')],
'report': [('from','from'),('until','until')],
'card': [('ref','client')],
'pdf': [('ref','ref')],
'quote_status': [('ref','ref'),('status','quote_status')],
'photo': [('ref','product')],
'editproduct': [('product','product'),('name','name'),('brand','brand'),('size','size'),('price','price'),('photo','photo')],
'minimum': [('product','product'),('point','point'),('minimum','minimum')],
'debt_due': [('sale','sale'),('debt_due','debt_due')],
'cancel_sale': [('sale','sale'),('reason','cancel_reason'),('settlement','settlement')],
}

class API:
    def __init__(self,token):
        self.base='https://api.telegram.org/bot'+token+'/'

    def call(self,method,data):
        req=urllib.request.Request(self.base+method,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=35) as r:
            result=json.load(r)
        if not result.get('ok'):
            raise RuntimeError('Telegram API request failed')
        return result['result']

    def document(self,chat,data,filename):
        boundary='----TopshinalarUploadBoundary'
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
        req=urllib.request.Request(self.base+'sendDocument',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
        with urllib.request.urlopen(req,timeout=35) as r:
            result=json.load(r)
        if not result.get('ok'):
            raise RuntimeError('Telegram document failed')

    def photo(self,chat,data,caption='',keyboard=None):
        boundary='TopshinalarPhoto'+os.urandom(12).hex()
        fields={'chat_id':str(chat),'caption':caption}
        if keyboard:fields['reply_markup']=json.dumps(keyboard,ensure_ascii=False)
        body=b''
        for name,value in fields.items():
            body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
        body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="tyre.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
        req=urllib.request.Request(self.base+'sendPhoto',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
        with urllib.request.urlopen(req,timeout=35) as response:result=json.load(response)
        if not result.get('ok'):raise RuntimeError('Telegram photo failed')


class Bot(Usability):
    def __init__(self,store):
        self.s=store
        self.s.db.execute('CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0)')
        self.s.db.commit()

    def lang(self,uid):
        return self.s.user(uid)['lang']

    def command_allowed(self,uid,cmd):
        try:require_command(self.s,uid,cmd);return True
        except PermissionError:return False

    def keyboard(self,uid):
        u=self.s.user(uid)
        keys=[k for k in MENU if (u['role']=='director' or k not in DIRECTOR_ONLY) and self.command_allowed(uid,k)]
        rows=[[{'text':label(k,u['lang'])} for k in keys[i:i+2]] for i in range(0,len(keys),2)]
        url=os.environ.get('PUBLIC_APP_URL','')
        if url.startswith('https://'):
            rows.insert(0,[{'text':'📱 '+('Ilovani ochish' if u['lang']=='uz' else 'Открыть приложение')}])
        return {'keyboard':rows,'resize_keyboard':True}

    def queue(self,uid,text=None,document=None,filename=None,photo=None,keyboard=None):
        if document is not None:
            payload={'document':base64.b64encode(document).decode(),'filename':filename}
        elif photo:
            payload={'photo':photo,'caption':text or ''}
        else:
            # Telegram's message limit; preserve complete lists in consecutive messages.
            chunks=[]; current=''
            for line in str(text).splitlines(keepends=True):
                for pos in range(0,len(line),3500):
                    part=line[pos:pos+3500]
                    if len(current)+len(part)>3500:
                        chunks.append(current);current=''
                    current+=part
            chunks.append(current or ' ')
            for chunk in chunks:
                p={'text':chunk}
                if keyboard: p['reply_markup']=keyboard
                self.s.add('outbox',chat=uid,payload=json.dumps(p,ensure_ascii=False))
            return
        if keyboard:payload['reply_markup']=keyboard
        self.s.add('outbox',chat=uid,payload=json.dumps(payload,ensure_ascii=False))

    def session(self,uid):
        row=self.s.db.execute('SELECT data FROM sessions WHERE user_id=?',(uid,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_session(self,uid,state):
        if state is None:
            self.s.db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        else:
            self.s.db.execute('INSERT INTO sessions VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',(uid,json.dumps(state)))

    def directors(self,text):
        for u in self.s.rows("SELECT id FROM users WHERE role='director' AND active=1"):
            self.queue(u['id'],text)

    def process(self,update):
        from staff import StaffAccess, require_command, permissions
        message=update.get('message',{})
        if 'callback_query' in update:
            cb=update['callback_query'];source=cb.get('message',{})
            message={'from':cb.get('from',{}),'chat':source.get('chat',{}),'_callback':cb.get('data','')}
        uid=message.get('from',{}).get('id')
        chat=message.get('chat',{})
        if not uid or chat.get('type')!='private':
            # Never expose employee/client data in Telegram groups.
            return
        if self.s.db.execute('SELECT 1 FROM updates WHERE id=?',(update['update_id'],)).fetchone():
            return
        invite=re.fullmatch(r'/start(?:@[A-Za-z0-9_]+)? staff_([A-Za-z0-9_-]+)',message.get('text','').strip())
        try:
            with self.s.db:
                self.s.db.execute('BEGIN IMMEDIATE')
                name=' '.join(filter(None,[message['from'].get('first_name'),message['from'].get('last_name')])) or str(uid)
                if invite:
                    StaffAccess(self.s).accept(invite[1],uid,name)
                    message={**message,'text':'/start'}
                self.s.user(uid)
                self.s.db.execute('UPDATE users SET name=? WHERE id=?',(name[:150],uid))
                self.route(uid,message)
                if invite:
                    role=self.s.user(uid)['role']
                    self.queue(uid,('Direktor sifatida qo‘shildingiz.\nВы добавлены как директор.' if role=='director' else 'Xodim sifatida qo‘shildingiz.\nВы добавлены как сотрудник.')+'\n/app')
                self.s.add('updates',id=update['update_id'],created=now())
        except (ValueError,PermissionError,sqlite3.IntegrityError) as exc:
            with self.s.db:
                try:
                    lang=self.lang(uid)
                    if isinstance(exc,PermissionError):
                        text=tr('denied',lang,id=uid)
                    else:
                        reason=ERRORS.get(str(exc),('ma’lumotni tekshiring; /cancel bilan qayta boshlang','проверьте данные; начните заново через /cancel'))[lang=='ru']
                        text=tr('error',lang,reason=reason)
                except (ValueError,PermissionError):
                    text=tr('denied','uz',id=uid)
                if invite:
                    reason=ERRORS.get(str(exc),ERRORS['invite_invalid'])
                    text='Kirish yopiq. '+reason[0]+'\nДоступ закрыт. '+reason[1]
                self.queue(uid,text)
                self.s.add('updates',id=update['update_id'],created=now())

    def route(self,uid,message):
        lang=self.lang(uid); text=message.get('text','').strip()
        if '_callback' in message:
            self.ui_callback(uid,message['_callback']);return
        if text in {'/cancel',tr('cancel',lang)}:
            self.set_session(uid,None);self.queue(uid,tr('cancelled',lang),keyboard=self.keyboard(uid));return
        if text in {'/back',tr('back',lang)}:
            self.go_back(uid);return
        command=text.split()[0].split('@')[0][1:] if text.startswith('/') else next((k for k in MENU if text==label(k,lang)),None)
        if command=='app' or text in {'📱 Ilovani ochish','📱 Открыть приложение'}:
            url=os.environ.get('PUBLIC_APP_URL','')
            title='📱 '+('Ilovani ochish' if lang=='uz' else 'Открыть приложение')
            if url.startswith('https://'):
                self.queue(uid,title,keyboard={'inline_keyboard':[[{'text':title,'web_app':{'url':url}}]]})
            else:self.queue(uid,'Mini App URL sozlanmagan / URL Mini App не настроен')
            return
        if command in {'start','help'}:
            self.set_session(uid,None)
            helptext=tr('hello',lang)+'\n\n'+('\n'.join('/'+k+' — '+label(k,lang) for k in MENU if (self.s.user(uid)['role']=='director' or k not in DIRECTOR_ONLY) and self.command_allowed(uid,k)))
            helptext+='\n/points /card /done /pdf /quote_status /delivery_status /photo /return /writeoff /cancel\n/stock <search> | /clients <search>'
            self.queue(uid,helptext,keyboard=self.keyboard(uid));return
        if command=='language':
            self.set_session(uid,{'cmd':'language'})
            self.queue(uid,'Tilni tanlang / Выберите язык',keyboard={'keyboard':[[{'text':'O‘zbekcha'},{'text':'Русский'}]],'resize_keyboard':True});return
        state=self.session(uid)
        if state and state['cmd']=='language':
            if text not in {'O‘zbekcha','Русский'}:
                raise ValueError('language')
            lang='ru' if text=='Русский' else 'uz'
            self.s.db.execute('UPDATE users SET lang=? WHERE id=?',(lang,uid));self.set_session(uid,None)
            self.queue(uid,tr('hello',lang),keyboard=self.keyboard(uid));return
        # Lookup commands remain usable during a dialog.
        if command:require_command(self.s,uid,command)
        if state:require_command(self.s,uid,state['cmd'])
        if command in {'clients','stock','points','staff','tasks','quotes'}:
            self.listing(uid,command,text.partition(' ')[2] if text.startswith('/') else '')
            return
        if command in {'debts','overdue','summary','lowstock'}:
            self.ux_listing(uid,command);return
        if command:
            if command in DIRECTOR_ONLY:
                self.s.director(uid)
            if command=='startwork':
                self.s.start(uid);self.queue(uid,tr('started',lang))
                self.notify_shift(uid,'start');return
            if command in FORMS:
                state={'cmd':command,'step':0,'data':{},'version':3}
                self.set_session(uid,state);self.prompt(uid,state);return
            self.queue(uid,tr('choose',lang));return
        if not state:
            if text:self.show_catalog(uid,text)
            else:self.queue(uid,tr('choose',lang),keyboard=self.keyboard(uid))
            return
        if state.get('item_stage'):
            self.cart_input(uid,state,text);return
        if state['cmd'] in {'sell','quote'} and any(int(row.get('discount',0)) != 0 for row in state['data'].get('items',[])):
            self.set_session(uid,None)
            self.queue(uid,tr('discount_removed',lang),keyboard=self.keyboard(uid))
            return
        if state['cmd']=='quote' and state.get('version')!=3:
            data={k:v for k,v in state['data'].items() if k in {'client','items'}}
            step=0 if 'client' not in data else (1 if 'items' not in data else 2)
            state={'cmd':'quote','step':step,'data':data,'version':3}
            self.set_session(uid,state);self.prompt(uid,state);return
        fields=FORMS[state['cmd']]
        if state['step']>=len(fields):
            if text!=tr('confirm',lang):
                self.queue(uid,tr('check',lang));return
            ref=self.execute(uid,state['cmd'],state['data'])
            self.set_session(uid,None)
            self.queue(uid,tr('ok',lang,id=ref or '-'),keyboard=self.keyboard(uid));return
        key=fields[state['step']][0]
        if self.typed_picker(uid,state,key,text):return
        value=self.validate(uid,state['cmd'],key,text,message)
        state['data'][key]=value;state['step']+=1
        self.set_session(uid,state);self.prompt(uid,state)

    def prompt(self,uid,state):
        lang=self.lang(uid);fields=FORMS[state['cmd']]
        if state['step']<len(fields):
            if state.get('item_stage'):
                self.cart_prompt(uid,state);return
            if fields[state['step']][0]=='items' and state.get('preset_product'):
                state['item_stage']='qty';state['selected_product']=state.pop('preset_product');state.setdefault('cart',[])
                self.set_session(uid,state);self.cart_prompt(uid,state);return
            buttons=[[{'text':tr('back',lang)},{'text':tr('cancel',lang)}]]
            if fields[state['step']][0]=='payment':
                buttons=[[{'text':name}] for name in payment_labels(lang)]+buttons
            if fields[state['step']][0]=='fulfillment':
                buttons=[[{'text':name}] for name in fulfillment_labels(lang)]+buttons
            if fields[state['step']][0]=='settlement':
                buttons=[[{'text':tr('refund_yes',lang)}]]+buttons
            prompt_text=tr(fields[state['step']][1],lang)
            if state['cmd']=='pay' and fields[state['step']][0]=='amount':
                prompt_text=prompt_text.replace('USD',self.s.one('sales',state['data']['sale'])['currency'])
            self.queue(uid,prompt_text,keyboard={'keyboard':buttons,'resize_keyboard':True})
            self.prompt_extras(uid,state)
        else:
            # Human-readable preview contains names as well as internal IDs.
            lines=[]
            for key,val in state['data'].items():
                if key=='items':
                    for row in self.s.items(val):
                        lines.append(f"{row['name']} × {row['qty']} | {fmt(row['price'])} USD | {fmt(row['total'])} USD")
                    lines.append(('Jami: ' if lang=='uz' else 'Итого: ')+fmt(sum(x['total'] for x in self.s.items(val)))+' USD')
                    if state['cmd']=='quote' and state['data'].get('exchange_rate'):
                        from core import exchange_rate
                        from decimal import Decimal, ROUND_HALF_UP
                        rate=exchange_rate(state['data']['exchange_rate'])
                        total=sum(int((Decimal(x['price'])*rate).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*x['qty'] for x in self.s.items(val))
                        lines.append('1 USD = '+str(rate)+' UZS | '+fmt(total)+' UZS')
                elif key=='photo':
                    pass
                else:
                    if key=='payment':val=payment_label(val,lang)
                    if key=='fulfillment':val=fulfillment_label(val,lang)
                    if key not in dict(fields):continue
                    prompt_key=dict(fields)[key]
                    title=tr(prompt_key,lang).split('\n')[0].split(':')[0]
                    if key in {'client','point','product'}:
                        table={'client':'clients','point':'points','product':'products'}[key]
                        val=f"#{val} {self.s.one(table,val)['name']}"
                    lines.append(f'{title}\n{val}')
            if state['cmd']=='sell':
                total=sum(x['total'] for x in self.s.items(state['data']['items']));paid=money(state['data']['paid'])
                if paid>total:raise ValueError('paid')
                lines.append(tr('payment_summary',lang,total=fmt(total),paid=fmt(paid),debt=fmt(total-paid)))
            if state['cmd']=='cancel_sale':
                row=self.s.one('sales',state['data']['sale'])
                state['data']['_expected_paid']=row['paid'];self.set_session(uid,state)
                lines.append(tr('cancel_preview',lang,amount=fmt(row['paid'])).replace('USD',row['currency']))
            self.queue(uid,'\n\n'.join(lines)+'\n\n'+tr('check',lang),keyboard={'keyboard':[[{'text':tr('confirm',lang)}],[{'text':tr('back',lang)},{'text':tr('cancel',lang)}]],'resize_keyboard':True})

    def validate(self,uid,cmd,key,text,message):
        if key=='photo':
            if message.get('photo'):
                return message['photo'][-1]['file_id']
            if text=='-':return None
            raise ValueError('photo')
        if cmd=='editproduct' and key in {'name','brand','size','price'} and text=='-':
            state=self.session(uid);product=self.s.one('products',state['data']['product'])
            if key=='price':
                if product['currency']!='USD':raise ValueError('amount')
                return fmt(product['price']).replace(' ','')
            return product[key]
        if not text or len(text)>3000:
            raise ValueError('text')
        if key=='items':
            try:
                rows=parse_item_lines(text)
                self.s.items(rows)
                return rows
            except (ValueError,TypeError):
                raise ValueError('items') from None
        if key in {'product','client','point'}:
            value=integer(text); self.s.one({'product':'products','client':'clients','point':'points'}[key],value);return value
        if key=='qty':return integer(text)
        if key=='minimum':
            if not re.fullmatch(r'\d{1,7}',text) or int(text)>1000000:raise ValueError('quantity')
            return int(text)
        if key=='debt_due':
            if text=='-':return ''
            try:text=datetime.strptime(text,'%Y-%m-%d').date().isoformat()
            except ValueError:raise ValueError('date') from None
            return text
        if key=='settlement':
            if text!=tr('refund_yes',self.lang(uid)):raise ValueError('refund_required')
            return True
        if key=='reason' and cmd=='cancel_sale' and text=='-':raise ValueError('reason')
        if key=='exchange_rate':
            from core import exchange_rate
            return str(exchange_rate(text))
        if key in {'price','amount','paid','fee'}:
            money(text,key=='amount');return text
        if key=='payment':return normalize_payment(text)
        if key=='fulfillment':return normalize_fulfillment(text)
        if key=='phone':
            phone=re.sub(r'[\s()-]','',text)
            if not re.fullmatch(r'\+?\d{9,15}',phone):raise ValueError('phone')
            return phone
        if key in {'employee','assignee'}:
            target=uid if text=='0' and key=='assignee' else int(text)
            self.s.user(target)
            if target!=uid:self.s.director(uid)
            return target
        if key=='sale':
            if cmd=='delivery' and text=='0':return None
            value=integer(text);sale=self.s.one('sales',value)
            if sale['status']!='active':raise ValueError('sale_cancelled')
            if cmd=='debt_due':self.s.own(uid,sale)
            return value
        if key=='ref':
            value=integer(text)
            table={'card':'clients','done':'tasks','pdf':'quotes','quote_status':'quotes','quote_options':'quotes','delivery_status':'deliveries','photo':'products'}[cmd]
            row=self.s.one(table,value)
            if table in {'tasks','quotes','deliveries'}:self.s.own(uid,row)
            return value
        if key in {'from','until'}:
            try:datetime.strptime(text,'%Y-%m-%d')
            except ValueError:raise ValueError('date') from None
        if key=='due':
            try:
                d=datetime.strptime(text,'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
                if d<=datetime.now(TZ):raise ValueError()
            except ValueError:raise ValueError('date') from None
        if key=='status':
            allowed={'new','on_way','delivered','cancelled'} if cmd=='delivery_status' else {'draft','sent','accepted','rejected'}
            if text not in allowed:raise ValueError('status')
        return '' if text=='-' else text

    def execute(self,uid,cmd,d):
        require_command(self.s,uid,cmd)
        if cmd=='editproduct':return self.s.edit_product(uid,**d)
        if cmd=='minimum':return self.s.set_minimum(uid,**d)
        if cmd=='debt_due':return self.s.set_debt_due(uid,**d)
        if cmd=='cancel_sale':return self.s.cancel_sale(uid,d['sale'],d['reason'],d['settlement'],d.get('_expected_paid'))
        if cmd=='newclient':return self.s.client(uid,**d)
        if cmd=='newpoint':
            self.s.director(uid)
            ref=self.s.add('points',**d);self.s.log(uid,'point',ref);return ref
        if cmd=='newproduct':return self.s.product(uid,**d)
        if cmd in {'income','return','writeoff'}:
            return self.s.move(uid,**d,kind={'income':'in','return':'return','writeoff':'writeoff'}[cmd])
        if cmd=='sell':
            ref=self.s.order(uid,**d)
            if self.s.one('sales',ref)['paid']<self.s.one('sales',ref)['total']:
                self.offer_due(uid,ref)
            return ref
        if cmd=='quote':
            ref=self.s.order(uid,**d,quote=True)
            self.pdf(uid,ref);return ref
        if cmd=='quote_options':
            ref=self.s.quote_options(uid,**d)
            self.pdf(uid,ref);return ref
        if cmd=='pay':return self.s.payment(uid,d['sale'],d['amount'],d['payment'])
        if cmd=='task':return self.s.task(uid,**d)
        if cmd=='done':self.s.complete_task(uid,d['ref']);return d['ref']
        if cmd=='call':return self.s.call(uid,**d)
        if cmd=='delivery':return self.s.delivery(uid,**d)
        if cmd=='delivery_status':self.s.delivery_status(uid,**d);return d['ref']
        if cmd=='fine':return self.s.fine(uid,**d)
        if cmd=='endwork':
            self.s.end(uid,d['report']);self.notify_shift(uid,'end',d['report'])
            today=now()[:10]
            if 'reports' in permissions(self.s,uid):self.make_report(uid,today,today)
            return
        if cmd=='report':self.make_report(uid,d['from'],d['until']);return
        if cmd=='card':
            self.xlsx(uid,self.s.client_card(uid,d['ref']),f'client-{d["ref"]}.xlsx');return d['ref']
        if cmd=='pdf':self.pdf(uid,d['ref']);return d['ref']
        if cmd=='quote_status':
            row=self.s.one('quotes',d['ref']);self.s.own(uid,row)
            self.s.db.execute('UPDATE quotes SET status=? WHERE id=?',(d['status'],d['ref']));self.s.log(uid,cmd,d['ref']);return d['ref']
        if cmd=='photo':
            p=self.s.one('products',d['ref'])
            if p['photo']:self.queue(uid,p['name'],photo=p['photo'])
            else:self.queue(uid,tr('empty',self.lang(uid)))
            return d['ref']
        raise ValueError('command')

    def listing(self,uid,cmd,query):
        if cmd=='stock':self.show_catalog(uid,query)
        elif cmd=='clients':self.show_entities(uid,'clients',query)
        else:self.show_records(uid,cmd,query)

    def pretty_row(self,row,lang):
        from reports import COLUMNS, localized
        return ' | '.join(f'{COLUMNS.get(k,(k,k))[lang=="ru"]}: {fmt(v)+" "+row.get("currency","USD") if k=="total" else localized(k,v,lang)}' for k,v in row.items())

    def pdf(self,uid,ref):
        from quotation import quotation_pdf
        self.queue(uid,document=quotation_pdf(self.s,uid,ref),filename=f'TOPSHINALAR-KP-{ref}.pdf')

    def xlsx(self,uid,sections,filename):
        from reports import workbook
        sections=self.enrich(sections)
        self.queue(uid,document=workbook(sections,self.lang(uid)),filename=filename)

    def enrich(self,sections):
        result={}
        for name,rows in sections.items():
            out=[]
            for row in rows:
                r=dict(row)
                if type(r.get('point')) is int:
                    r['warehouse_name']=self.s.one('points',r['point'])['name']
                for key,table,destination in [('client','clients','client_name'),('actor','users','employee_name'),('owner','users','owner_name'),('approved_by','users','approved_by_name'),('cancelled_by','users','cancelled_by_name')]:
                    if key in r and r[key] is not None:
                        r[destination]=self.s.one(table,r[key])['name']
                        if table=='users' and r[destination].strip()==str(r[key]):
                            r[destination]=''
                if name in {'sales','deliveries'}:
                    r['debt']=0 if r.get('status')=='cancelled' else r.get('total',r.get('fee',0))-r['paid']
                out.append(r)
            result[name]=out
        return result

    def make_report(self,uid,start,end,section='all'):
        require_command(self.s,uid,'report')
        from reports import report_group, SECTIONS
        labels,fields=report_group(section)
        data=self.s.report(uid,start,end)
        if section!='all':
            lang=self.lang(uid)
            if section=='stock':
                selected=self.s.inventory_report(uid)
            elif section=='debts':
                sale_ids={row['id'] for row in data['sales']}
                selected={'debts':[row for row in self.s.debts(uid) if row['id'] in sale_ids]}
            else:
                selected={name:data[name] for name in fields}
            title=labels[lang=='ru']+'\n'+start+' — '+end
            title+='\n'+'\n'.join(SECTIONS[name][lang=='ru']+': '+str(len(rows)) for name,rows in selected.items())
            if section in {'stock','tasks'}:
                title+='\n'+('Joriy holat. Sana oralig‘i bu bo‘limni cheklamaydi.' if lang=='uz' else 'Текущее состояние. Период не ограничивает этот раздел.')
            elif section=='debts':
                title+='\n'+('Shu davrda sotilgan savdolarning hozirgi qolgan qarzi.' if lang=='uz' else 'Текущий остаток долга по продажам выбранного периода.')
            self.queue(uid,title)
            self.xlsx(uid,selected,f'TOPSHINALAR-{section}-{start}-{end}.xlsx')
            return
        active=[s for s in data['sales'] if s.get('status')!='cancelled' and s['currency']=='USD']
        total=sum(s['total'] for s in active); paid=sum(s['paid'] for s in active)
        received=sum(p['amount'] for p in data['payments'] if p['currency']=='USD')
        lang=self.lang(uid)
        title=(f'Hisobot: {start} — {end}\nSotuvlar: {len(data["sales"])}\nSotilgan summa: {fmt(total)} USD\nShu sotuvlardan to‘langan: {fmt(paid)} USD\nShu sotuvlardan qolgan qarz: {fmt(total-paid)} USD\nDavrda kelib tushgan to‘lovlar: {fmt(received)} USD\nQo‘ng‘iroqlar: {len(data["calls"])}' if lang=='uz' else f'Отчет: {start} — {end}\nПродажи: {len(data["sales"])}\nСумма продаж: {fmt(total)} USD\nОплачено по этим продажам: {fmt(paid)} USD\nОстаток долга по этим продажам: {fmt(total-paid)} USD\nПоступления за период: {fmt(received)} USD\nЗвонки: {len(data["calls"])}')
        if any(s['currency']=='UZS' for s in data['sales']):
            title+='\n'+('Oldingi so‘m yozuvlari jamiga kiritilmadi; Excelda valyutasi bilan saqlangan.' if lang=='uz' else 'Прежние записи в сумах не включены в итоги USD; валюта сохранена в Excel.')
        self.queue(uid,title)
        refunds=sum(p['amount'] for p in data['refunds'] if p['currency']=='USD')
        self.queue(uid,tr('refund_summary',lang,refunds=fmt(refunds),net=fmt(received-refunds)))
        data.update(self.s.inventory_report(uid))
        self.xlsx(uid,data,f'TOPSHINALAR-{start}-{end}.xlsx')

    def notify_shift(self,uid,event,report=''):
        user=self.s.user(uid)
        for director in self.s.rows("SELECT * FROM users WHERE role='director' AND active=1"):
            ru=director['lang']=='ru'
            title=('Начало работы' if event=='start' else 'Завершение работы') if ru else ('Ish boshlandi' if event=='start' else 'Ish tugadi')
            self.queue(director['id'],f'{title}\n{user["name"]} ({uid})\n{now()}\n{report}')
            if event=='end':
                data=self.s.report(uid,now()[:10],now()[:10])
                # A director ending their own shift still sends only that user's day here.
                data={k:[r for r in rows if r.get('actor')==uid] for k,rows in data.items()}
                self.xlsx(director['id'],data,f'TOPSHINALAR-day-{uid}-{now()[:10]}.xlsx')

    def schedule(self):
        with self.s.db:
            rows=self.s.rows("SELECT t.*,c.name client_name,u.lang FROM tasks t JOIN clients c ON c.id=t.client JOIN users u ON u.id=t.actor WHERE t.status='open' AND t.notified=0 AND t.due<=? AND u.active=1",(now(),))
            for row in rows:
                self.queue(row['actor'],tr('reminder',row['lang'],id=row['id'],client=row['client_name'],due=row['due'],note=row['note']))
                self.s.db.execute('UPDATE tasks SET notified=1 WHERE id=?',(row['id'],))
            self.schedule_business()

    def drain(self,api):
        rows=self.s.rows('SELECT * FROM outbox WHERE sent=0 ORDER BY id LIMIT 100')
        failed_chats=set()
        for row in rows:
            if row['chat'] in failed_chats:continue
            try:
                # Access revocation also prevents queued private information delivery.
                try:self.s.user(row['chat'])
                except (ValueError,PermissionError):
                    p=json.loads(row['payload'])
                    if not p.get('text','').startswith(('Kirish yopiq.','Доступ закрыт.')):
                        with self.s.db:self.s.db.execute('UPDATE outbox SET sent=1 WHERE id=?',(row['id'],))
                        continue
                p=json.loads(row['payload'])
                if 'document' in p:api.document(row['chat'],base64.b64decode(p['document']),p['filename'])
                elif 'photo' in p:
                    path=local_photo(p['photo'])
                    if path:api.photo(row['chat'],path.read_bytes(),p.get('caption',''),p.get('reply_markup'))
                    else:api.call('sendPhoto',{'chat_id':row['chat'],**p})
                else:api.call('sendMessage',{'chat_id':row['chat'],**p})
                with self.s.db:self.s.db.execute('UPDATE outbox SET sent=1 WHERE id=?',(row['id'],))
            except Exception:
                failed_chats.add(row['chat'])
                logging.warning('Delivery deferred for outbox record %s',row['id'])


def ids(name):
    raw=os.environ.get(name,'')
    values=[int(v.strip()) for v in raw.split(',') if v.strip()]
    if len(values)!=len(set(values)) or any(v<=0 for v in values):raise ValueError('Invalid user IDs')
    return values


def run_bot():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    token=os.environ.get('BOT_TOKEN','')
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):
        raise SystemExit('Set BOT_TOKEN in the environment. Never commit it.')
    path=os.environ.get('DB_PATH','data/topshinalar.sqlite3')
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    s=Store(path);s.configure(ids('DIRECTOR_IDS'),ids('EMPLOYEE_IDS'))
    import_catalog(s)
    bot=Bot(s);api=API(token)
    # Refuse to disrupt another deployment's webhook.
    if api.call('getWebhookInfo',{}).get('url'):
        raise SystemExit('This token has an active webhook. Use a separate token or deliberately migrate it first.')
    info=api.call('getMe',{})
    with s.db:s.db.execute("INSERT INTO meta VALUES('bot_username',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(info['username'],))
    while True:
        try:
            bot.schedule();bot.drain(api)
            row=s.db.execute("SELECT value FROM meta WHERE key='offset'").fetchone()
            offset=int(row[0]) if row else 0
            updates=api.call('getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message','callback_query']})
            for update in updates:
                try:
                    bot.process(update)
                    if 'callback_query' in update:
                        try:api.call('answerCallbackQuery',{'callback_query_id':update['callback_query']['id']})
                        except Exception:pass
                except Exception:
                    # Do not print message contents, HTTP URLs or tokens.
                    logging.error('Update %s failed; retrying without advancing offset',update.get('update_id'))
                    time.sleep(2);break
                with s.db:s.db.execute("INSERT INTO meta VALUES('offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(update['update_id']+1),))
            # Remove delivered payloads; domain/audit records remain.
            with s.db:
                s.db.execute('DELETE FROM outbox WHERE sent=1')
        except KeyboardInterrupt:break
        except Exception:
            logging.warning('Connection unavailable; retrying in 5 seconds')
            time.sleep(5)

def main():
    # Shared by direct Python, systemd and Docker starts using the same database.
    path=os.path.realpath(os.environ.get('DB_PATH','data/topshinalar.sqlite3'))
    with SingleInstance(path+'.lock'):
        run_bot()

if __name__=='__main__':main()
