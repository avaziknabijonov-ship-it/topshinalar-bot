from staff import require_command
"""Product cards, paged selectors and business notifications for the staff bot."""
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta
from core import fmt, integer, money, now, TZ
from i18n import tr


IMPERIAL_RE = re.compile(r'(?<![\w.])(\d{1,2}(?:[.,]\d{1,2})?)\s*([rр-])\s*(\d{2}(?:[.,]\d+)?)(?![\d.])',re.I)

SIZE_RE = re.compile(r'(?<!\w)(\d{3})\s*[/xх\s-]\s*(100|[1-9]\d)(?![\d.,])(?:\s*[rр]\s*(\d{2}(?:[.,]\d+)?))?', re.I)

def size_parts(text):
    match=SIZE_RE.search(text)
    return match.groups() if match else None


def matches_product(query,row):
    hay=' '.join(str(row.get(k) or '') for k in ('name','brand','size','point'))
    if not query.strip():return True
    wanted=size_parts(query)
    if wanted:
        found=size_parts(str(row.get('size') or '')+' '+row['name'])
        if not found or wanted[:2]!=found[:2]:return False
        if wanted[2] and (not found[2] or wanted[2].replace(',','.')!=found[2].replace(',','.')):return False
        # Preserve any brand or other words supplied alongside a size.
        rest=SIZE_RE.sub(' ',query.casefold())
        return all(word in hay.casefold() for word in rest.split())
    imperial=IMPERIAL_RE.search(query)
    if imperial:
        found=IMPERIAL_RE.search(str(row.get('size') or '')+' '+row['name'])
        normalize=lambda m:(m[1].replace(',','.'),m[2].casefold().replace('р','r'),m[3].replace(',','.'))
        if not found or normalize(imperial)!=normalize(found):return False
        rest=IMPERIAL_RE.sub(' ',query.casefold())
        return all(word in hay.casefold() for word in rest.split())
    return all(word in hay.casefold() for word in query.casefold().split())


class Usability:
    def words(self,uid,uz,ru):return ru if self.lang(uid)=='ru' else uz

    def fingerprint(self,uid):
        return hashlib.sha256(json.dumps(self.session(uid),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def inline(self,uid,rows,guard=False):
        token=secrets.token_hex(6)
        options=[];keyboard=[]
        for row in rows:
            buttons=[]
            for title,action in row:
                index=len(options);options.append(action)
                buttons.append({'text':str(title)[:64],'callback_data':f'ui:{token}:{index}'})
            if buttons:keyboard.append(buttons)
        data={'options':options,'guard':self.fingerprint(uid) if guard else None}
        self.s.add('ui_views',token=token,user_id=uid,data=json.dumps(data))
        self.s.db.execute('DELETE FROM ui_views WHERE user_id=? AND token NOT IN (SELECT token FROM ui_views WHERE user_id=? ORDER BY rowid DESC LIMIT 100)',(uid,uid))
        return {'inline_keyboard':keyboard}

    def start_form(self,uid,cmd,data=None,step=0,**extras):
        require_command(self.s,uid,cmd)
        from bot import FORMS
        from i18n import DIRECTOR_ONLY
        if cmd in DIRECTOR_ONLY:self.s.director(uid)
        state={'cmd':cmd,'step':step,'data':data or {},'version':2,**extras}
        if cmd not in FORMS:raise ValueError('command')
        self.set_session(uid,state);self.prompt(uid,state)

    def ui_callback(self,uid,data):
        match=re.fullmatch(r'ui:([a-f0-9]{12}):(\d{1,3})',data)
        if not match:self.queue(uid,tr('stale',self.lang(uid)));return
        row=self.s.db.execute('SELECT data FROM ui_views WHERE token=? AND user_id=?',(match[1],uid)).fetchone()
        if not row:self.queue(uid,tr('stale',self.lang(uid)));return
        view=json.loads(row[0]);index=int(match[2])
        if index>=len(view['options']) or (view['guard'] and view['guard']!=self.fingerprint(uid)):
            self.queue(uid,tr('stale',self.lang(uid)));return
        action=view['options'][index];op=action['op']
        current=self.session(uid)
        if current:require_command(self.s,uid,current['cmd'])
        if op=='photo':require_command(self.s,uid,'photo')
        if op=='catalog':self.show_catalog(uid,action['query'],action['page']);return
        if op=='picker':self.show_picker(uid,self.session(uid),action['key'],action['query'],action['page']);return
        if op=='entities':self.show_entities(uid,action['kind'],action.get('query',''),action['page']);return
        if op=='records':self.show_records(uid,action['kind'],action['query'],action['page']);return
        if op=='pick':
            state=self.session(uid)
            if not state:raise ValueError('missing')
            self.route(uid,{'text':str(action['id'])});return
        if op=='cart_begin':
            state=self.session(uid);state['item_stage']='pick';state.setdefault('cart',[])
            self.set_session(uid,state);self.cart_prompt(uid,state);return
        if op=='cart_add':
            state=self.session(uid);state['item_stage']='pick'
            self.set_session(uid,state);self.cart_prompt(uid,state);return
        if op=='cart_finish':
            state=self.session(uid)
            if not state.get('cart'):raise ValueError('items')
            state['data']['items']=state.pop('cart');state['step']+=1
            for key in ('item_stage','selected_product','selected_qty'):state.pop(key,None)
            self.set_session(uid,state);self.prompt(uid,state);return
        if op=='photo':
            p=self.s.one('products',action['id'])
            if p['photo']:self.queue(uid,p['name'][:900],photo=p['photo'])
            else:self.queue(uid,tr('no_photo',self.lang(uid)))
            return
        if op=='form_ref':
            if self.session(uid):self.queue(uid,tr('busy',self.lang(uid)));return
            ref=self.validate(uid,action['cmd'],'ref',str(action['id']),{})
            self.start_form(uid,action['cmd'],{'ref':ref},1);return
        if op in {'sell_product','quote_product','edit','due','pay','void'}:
            if self.session(uid):self.queue(uid,tr('busy',self.lang(uid)));return
            ref=action['id']
            if op in {'sell_product','quote_product'}:
                self.s.one('products',ref)
                self.start_form(uid,'sell' if op=='sell_product' else 'quote',preset_product=ref)
            elif op=='edit':self.start_form(uid,'editproduct',{'product':ref},1)
            elif op=='due':
                row=self.s.one('sales',ref);self.s.own(uid,row)
                self.start_form(uid,'debt_due',{'sale':ref},1)
            elif op=='pay':self.start_form(uid,'pay',{'sale':ref},1)
            elif op=='void':self.start_form(uid,'cancel_sale',{'sale':ref},1)

    def show_catalog(self,uid,query='',page=0):
        require_command(self.s,uid,'catalog')
        lang=self.lang(uid)
        rows=[r for r in self.s.stock(uid) if matches_product(query,r)]
        grouped={}
        for row in rows:grouped.setdefault(row['id'],[]).append(row)
        products=list(grouped.values());page=max(0,min(page,max(0,(len(products)-1)//4)))
        selected=products[page*4:(page+1)*4]
        if not selected:self.queue(uid,tr('empty',lang));return
        for stock in selected:
            p=stock[0];parts=size_parts(p['name'])
            size=p.get('size') or ('/'.join(parts[:2])+(' R'+parts[2] if parts[2] else '') if parts else '-')
            brand=p.get('brand') or p['name'].split()[0]
            lines=[p['name'],f"ID: {p['id']}",self.words(uid,'Brend','Бренд')+': '+brand,self.words(uid,'Razmer','Размер')+': '+size,self.words(uid,'Narx','Цена')+': '+(self.words(uid,'Kiritilmagan','Не указана') if p.get('price_pending') else f"{fmt(p['price'])} UZS")]
            pending=p.get('catalog_sku') and not any(r.get('stock_set') for r in stock)
            if pending:lines.append(self.words(uid,'Qoldiq kiritilmagan','Остаток не указан'))
            for r in ([] if pending else stock):
                if r['point_id'] is not None:lines.append(f"{r['point']}: {r['qty']} "+self.words(uid,'dona','шт.'))
            if pending:pass
            elif stock[0]['point_id'] is None:lines.append(tr('no_points',lang))
            else:lines.append(self.words(uid,'Jami','Всего')+f": {sum(r['qty'] for r in stock)}")
            actions=[[(self.words(uid,'💰 Sotish','💰 Продать'),{'op':'sell_product','id':p['id']}),(self.words(uid,'📄 КП tayyorlash','📄 Создать КП'),{'op':'quote_product','id':p['id']})],[(self.words(uid,'🖼 Rasmni ko‘rish','🖼 Посмотреть фото'),{'op':'photo','id':p['id']})]]
            if self.s.user(uid)['role']=='director':actions.append([(self.words(uid,'✏️ Tahrirlash','✏️ Изменить'),{'op':'edit','id':p['id']})])
            markup=self.inline(uid,actions)
            body='\n'.join(lines)
            if p['photo']:
                # Telegram captions are limited; retain the complete text separately.
                caption=body if len(body)<950 else p['name'][:650]+f"\nID: {p['id']}"
                self.queue(uid,caption,photo=p['photo'],keyboard=markup)
                if caption!=body:self.queue(uid,body)
            else:self.queue(uid,body+'\n'+tr('no_photo',lang),keyboard=markup)
        nav=[]
        if page:nav.append((tr('previous',lang),{'op':'catalog','query':query,'page':page-1}))
        if (page+1)*4<len(products):nav.append((tr('next',lang),{'op':'catalog','query':query,'page':page+1}))
        if nav:self.queue(uid,f'{page+1} / {(len(products)+3)//4}',keyboard=self.inline(uid,[nav]))

    def picker_rows(self,uid,state,key,query=''):
        cmd=state['cmd']
        if key=='client' or (key=='ref' and cmd=='card'):
            rows=self.s.rows('SELECT id,name,phone FROM clients ORDER BY name,id')
        elif key=='point':rows=self.s.rows('SELECT id,name FROM points ORDER BY name,id')
        elif key=='product' or (key=='ref' and cmd=='photo') or key=='cart_product':
            rows=self.s.rows('SELECT id,name,brand,size FROM products WHERE active=1 ORDER BY name,id')
        elif key in {'employee','assignee'}:
            rows=self.s.rows('SELECT id,name FROM users WHERE active=1'+('' if self.s.user(uid)['role']=='director' else ' AND id=?')+' ORDER BY name',() if self.s.user(uid)['role']=='director' else (uid,))
        elif key=='sale':
            if cmd in {'pay','debt_due'}:rows=self.s.debts(uid)
            else:
                self.s.director(uid) if cmd=='cancel_sale' else self.s.user(uid)
                rows=self.s.rows("SELECT s.id,c.name,s.total,s.paid FROM sales s JOIN clients c ON c.id=s.client WHERE s.status='active' ORDER BY s.id DESC")
            rows=[dict(r,name=f"#{r['id']} {r.get('client_name',r.get('name',''))} | {fmt(r['total']-r['paid'])} UZS") for r in rows]
        elif key=='ref' and cmd in {'done','pdf','quote_status','quote_options','delivery_status'}:
            table='tasks' if cmd=='done' else 'deliveries' if cmd=='delivery_status' else 'quotes'
            scope='' if self.s.user(uid)['role']=='director' else ' WHERE r.actor=?'
            rows=self.s.rows(f'SELECT r.*,c.name client_name FROM {table} r JOIN clients c ON c.id=r.client'+scope+' ORDER BY r.id DESC',() if not scope else (uid,))
            rows=[dict(r,name=f"#{r['id']} {r['client_name']}") for r in rows]
        else:return None
        if key in {'product','cart_product'}:return [r for r in rows if matches_product(query,r)]
        return [r for r in rows if query.casefold() in (str(r.get('name',''))+' '+str(r.get('phone',''))).casefold()]

    def show_picker(self,uid,state,key,query='',page=0):
        rows=self.picker_rows(uid,state,key,query)
        if rows is None:return
        page=max(0,min(page,max(0,(len(rows)-1)//6)));chosen=rows[page*6:(page+1)*6]
        buttons=[[(f"{r['name'][:45]} · {r['id']}",{'op':'pick','id':r['id']})] for r in chosen]
        nav=[]
        if page:nav.append((tr('previous',self.lang(uid)),{'op':'picker','key':key,'query':query,'page':page-1}))
        if (page+1)*6<len(rows):nav.append((tr('next',self.lang(uid)),{'op':'picker','key':key,'query':query,'page':page+1}))
        if nav:buttons.append(nav)
        self.queue(uid,(tr('pick',self.lang(uid)) if chosen else tr('empty',self.lang(uid)))+f'\n{page+1} / {max(1,(len(rows)+5)//6)}',keyboard=self.inline(uid,buttons,True) if buttons else None)

    def typed_picker(self,uid,state,key,text):
        if not text or text.lstrip('+').isdigit():return False
        if self.picker_rows(uid,state,key) is None:return False
        self.show_picker(uid,state,key,text);return True

    def prompt_extras(self,uid,state):
        from bot import FORMS
        key=FORMS[state['cmd']][state['step']][0]
        self.show_picker(uid,state,key)
        if key=='items':
            self.queue(uid,tr('choose_items',self.lang(uid)),keyboard=self.inline(uid,[[(tr('choose_items',self.lang(uid)),{'op':'cart_begin'})]],True))
        if state['cmd']=='editproduct' and 'product' in state['data']:
            product=self.s.one('products',state['data']['product'])
            val=fmt(product[key]) if key=='price' else product.get(key)
            if val:self.queue(uid,self.words(uid,'Hozirgi qiymat: ','Сейчас: ')+str(val)+'\n'+self.words(uid,'O‘zgarmasa - yozing.','Для сохранения значения введите -.'))
        if key=='settlement':
            sale=self.s.one('sales',state['data']['sale'])
            self.queue(uid,tr('cancel_preview',self.lang(uid),amount=fmt(sale['paid'])))

    def go_back(self,uid):
        from bot import FORMS
        state=self.session(uid)
        if state and state.get('cmd')=='language':
            self.set_session(uid,None)
            self.queue(uid,tr('choose',self.lang(uid)),keyboard=self.keyboard(uid));return
        if not state or state.get('cmd') not in FORMS:
            self.queue(uid,tr('choose',self.lang(uid)),keyboard=self.keyboard(uid));return
        stage=state.get('item_stage')
        if stage:
            if stage=='price':state['item_stage']='qty';state.pop('selected_qty',None)
            elif stage=='qty':state['item_stage']='pick';state.pop('selected_product',None)
            elif stage=='review':
                previous=state['cart'].pop();state['selected_product']=previous['product'];state['selected_qty']=previous['qty'];state['item_stage']='price'
            else:
                for key in ('item_stage','cart','selected_product','selected_qty'):state.pop(key,None)
        elif state['step']>0:
            state['step']-=1
            keys=[key for key,_ in FORMS[state['cmd']][state['step']:]]
            for key in keys:state['data'].pop(key,None)
            if 'items' in keys:
                for key in ('cart','preset_product','item_stage'):state.pop(key,None)
        else:
            self.set_session(uid,None)
            self.queue(uid,tr('choose',self.lang(uid)),keyboard=self.keyboard(uid));return
        self.set_session(uid,state);self.prompt(uid,state)

    def cart_prompt(self,uid,state):
        lang=self.lang(uid);stage=state['item_stage']
        controls={'keyboard':[[{'text':tr('back',lang)},{'text':tr('cancel',lang)}]],'resize_keyboard':True}
        if stage=='pick':
            self.queue(uid,tr('choose_items',lang),keyboard=controls);self.show_picker(uid,state,'cart_product')
        elif stage=='qty':
            p=self.s.one('products',state['selected_product'])
            self.queue(uid,p['name']+'\n'+tr('qty',lang),keyboard=controls)
        elif stage=='price':
            p=self.s.one('products',state['selected_product'])
            value=fmt(p['price']).replace(' ','')
            if not p.get('price_pending'):controls['keyboard'].insert(0,[{'text':value}])
            shown=self.words(uid,'Kiritilmagan','Не указана') if p.get('price_pending') else fmt(p['price'])+' UZS'
            self.queue(uid,tr('price',lang)+'\n'+self.words(uid,'Katalogdagi narx: ','Цена в каталоге: ')+shown,keyboard=controls)
        else:
            lines=self.s.items(state['cart'])
            body='\n'.join(f"{p['name']} × {p['qty']} = {fmt(p['total'])} UZS" for p in lines)
            body+='\n'+self.words(uid,'Jami: ','Итого: ')+fmt(sum(p['total'] for p in lines))+' UZS'
            self.queue(uid,body,keyboard=self.inline(uid,[[(tr('add_item',lang),{'op':'cart_add'}),(tr('finish_items',lang),{'op':'cart_finish'})]],True))

    def cart_input(self,uid,state,text):
        stage=state['item_stage']
        if stage=='pick':
            if not text.isdigit():self.show_picker(uid,state,'cart_product',text);return
            product=integer(text);self.s.one('products',product)
            state['selected_product']=product;state['item_stage']='qty'
        elif stage=='qty':state['selected_qty']=integer(text);state['item_stage']='price'
        elif stage=='price':
            money(text)
            candidate=state.get('cart',[])+[{'product':state['selected_product'],'qty':state['selected_qty'],'price':text,'discount':0}]
            self.s.items(candidate);state['cart']=candidate;state['item_stage']='review'
        else:self.queue(uid,tr('check',self.lang(uid)));return
        self.set_session(uid,state);self.cart_prompt(uid,state)

    def offer_due(self,uid,ref):
        self.queue(uid,tr('due_offer',self.lang(uid)),keyboard=self.inline(uid,[[(self.words(uid,'📅 To‘lov muddati','📅 Срок оплаты'),{'op':'due','id':ref})]]))

    def show_entities(self,uid,kind,query='',page=0):
        require_command(self.s,uid,kind)
        lang=self.lang(uid)
        if kind=='clients':
            rows=self.s.rows('SELECT id,name,phone,owner FROM clients ORDER BY name,id')
            rows=[r for r in rows if query.casefold() in (r['name']+' '+r['phone']).casefold()]
        else:
            rows=self.s.debts(uid,kind=='overdue')
        page=max(0,min(page,max(0,(len(rows)-1)//6)));selected=rows[page*6:(page+1)*6]
        if not selected:self.queue(uid,tr('empty',lang));return
        for row in selected:
            if kind=='clients':self.queue(uid,f"#{row['id']} {row['name']}\n{row['phone']}")
            else:
                body=f"#{row['id']} {row['client_name']}\n{row['phone']}\n"+self.words(uid,'Qarz: ','Долг: ')+fmt(row['debt'])+' UZS\n'+self.words(uid,'Muddat: ','Срок: ')+(row['debt_due'] or tr('no_due',lang))
                actions=[[(self.words(uid,'💳 To‘lov','💳 Оплата'),{'op':'pay','id':row['id']})]]
                if self.s.user(uid)['role']=='director' or row['actor']==uid:actions.append([(self.words(uid,'📅 Muddat','📅 Срок'),{'op':'due','id':row['id']})])
                self.queue(uid,body,keyboard=self.inline(uid,actions))
        nav=[]
        if page:nav.append((tr('previous',lang),{'op':'entities','kind':kind,'query':query,'page':page-1}))
        if (page+1)*6<len(rows):nav.append((tr('next',lang),{'op':'entities','kind':kind,'query':query,'page':page+1}))
        if nav:self.queue(uid,f'{page+1} / {(len(rows)+5)//6}',keyboard=self.inline(uid,[nav]))

    def low_rows(self):
        return self.s.rows('SELECT l.*,p.name,t.name point_name,COALESCE(s.qty,0) qty FROM stock_limits l JOIN products p ON p.id=l.product JOIN points t ON t.id=l.point LEFT JOIN stock s ON s.product=l.product AND s.point=l.point WHERE p.active=1 AND l.minimum>0')

    def show_records(self,uid,kind,query='',page=0):
        require_command(self.s,uid,kind)
        lang=self.lang(uid)
        if kind=='staff':
            self.s.director(uid)
            rows=self.s.rows('SELECT id,name,role,lang FROM users WHERE active=1 ORDER BY name,id')
        elif kind=='points':rows=self.s.rows('SELECT id,name FROM points ORDER BY name,id')
        else:
            scope='' if self.s.user(uid)['role']=='director' else ' WHERE r.actor=?'
            rows=self.s.rows(f'SELECT r.*,c.name client_name FROM {kind} r JOIN clients c ON c.id=r.client'+scope+' ORDER BY r.id DESC',() if not scope else (uid,))
        if query:rows=[r for r in rows if query.casefold() in ' '.join(str(v) for v in r.values()).casefold()]
        page=max(0,min(page,max(0,(len(rows)-1)//6)))
        if not rows:
            self.queue(uid,tr('no_points' if kind=='points' else 'empty',lang));return
        for row in rows[page*6:(page+1)*6]:
            actions=[]
            if kind=='tasks' and row['status']=='open':actions=[[(self.words(uid,'✅ Bajarildi','✅ Выполнено'),{'op':'form_ref','cmd':'done','id':row['id']})]]
            if kind=='quotes':actions=[[(self.words(uid,'📄 PDF olish','📄 Скачать PDF'),{'op':'form_ref','cmd':'pdf','id':row['id']}),(self.words(uid,'✏️ Shartlar','✏️ Условия'),{'op':'form_ref','cmd':'quote_options','id':row['id']})]]
            self.queue(uid,self.pretty_row(row,lang),keyboard=self.inline(uid,actions) if actions else None)
        nav=[]
        if page:nav.append((tr('previous',lang),{'op':'records','kind':kind,'query':query,'page':page-1}))
        if (page+1)*6<len(rows):nav.append((tr('next',lang),{'op':'records','kind':kind,'query':query,'page':page+1}))
        if nav:self.queue(uid,f'{page+1} / {(len(rows)+5)//6}',keyboard=self.inline(uid,[nav]))

    def daily_summary(self,uid,date):
        self.s.director(uid);data=self.s.report(uid,date,date)
        sales=[r for r in data['sales'] if r['status']=='active']
        received=sum(r['amount'] for r in data['payments']);refunds=sum(r['amount'] for r in data['refunds'])
        debts=self.s.debts(uid)
        return self.words(uid,'KUNLIK XULOSA','ИТОГИ ДНЯ')+f' · {date}\n'+self.words(uid,'Sotuvlar','Продажи')+f": {len(sales)}\n"+self.words(uid,'Sotilgan summa','Сумма продаж')+f": {fmt(sum(r['total'] for r in sales))} UZS\n"+self.words(uid,'Pul tushumi','Поступления')+f': {fmt(received)} UZS\n'+tr('refund_summary',self.lang(uid),refunds=fmt(refunds),net=fmt(received-refunds))+'\n'+self.words(uid,'Jami qarz','Общая задолженность')+f": {fmt(sum(r['debt'] for r in debts))} UZS\n"+self.words(uid,'Qo‘ng‘iroqlar','Звонки')+f": {len(data['calls'])}\n"+self.words(uid,'Ochiq vazifalar','Открытые задачи')+f": {len(data['tasks'])}"

    def ux_listing(self,uid,command):
        require_command(self.s,uid,command)
        if command in {'debts','overdue'}:self.show_entities(uid,command);return
        self.s.director(uid)
        if command=='summary':self.queue(uid,self.daily_summary(uid,now()[:10]));return
        rows=[r for r in self.low_rows() if r['qty']<=r['minimum']]
        self.queue(uid,'\n\n'.join(f"{r['name']}\n{r['point_name']}: {r['qty']} / min {r['minimum']}" for r in rows) or tr('empty',self.lang(uid)))

    def once(self,key):
        cur=self.s.db.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',(key,now()))
        return bool(cur.rowcount)

    def schedule_business(self):
        stamp=now();today=stamp[:10];hour=int(stamp[11:13])
        directors=self.s.rows("SELECT * FROM users WHERE role='director' AND active=1")
        for r in self.low_rows():
            low=r['qty']<=r['minimum']
            if low and not r['alerted']:
                for d in directors:
                    self.queue(d['id'],self.words(d['id'],'KAM QOLDIQ','НИЗКИЙ ОСТАТОК')+f"\n{r['name']}\n{r['point_name']}: {r['qty']} / min {r['minimum']}")
            self.s.db.execute('UPDATE stock_limits SET alerted=? WHERE product=? AND point=?',(int(low),r['product'],r['point']))
        if hour>=9:
            rows=self.s.rows("SELECT s.*,c.name client_name,c.phone FROM sales s JOIN clients c ON c.id=s.client WHERE s.status='active' AND s.paid<s.total AND s.debt_due<>'' AND s.debt_due<=?",(today,))
            for row in rows:
                targets={d['id'] for d in directors}
                if self.s.one('users',row['actor'])['active']:targets.add(row['actor'])
                for target in targets:
                    if self.once(f'debt-reminder:{today}:{row["id"]}:{target}'):
                        self.queue(target,self.words(target,'TO‘LOV ESLATMASI','НАПОМИНАНИЕ ОБ ОПЛАТЕ')+f"\n#{row['id']} {row['client_name']}\n{row['phone']}\n{row['debt_due']}\n{fmt(row['total']-row['paid'])} UZS")
        # Report the completed previous day, including when a server missed midnight.
        yesterday=(datetime.fromisoformat(stamp).date()-timedelta(days=1)).isoformat()
        for d in directors:
            if self.once(f'daily-summary:{yesterday}:{d["id"]}'):
                self.queue(d['id'],self.daily_summary(d['id'],yesterday))
