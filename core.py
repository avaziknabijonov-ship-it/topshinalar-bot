"""Independent Telegram CRM. No connections to other business applications."""
import csv
import io
import json
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from payments import normalize_payment, normalize_fulfillment

TZ = ZoneInfo('Asia/Tashkent')

def now():
    return datetime.now(TZ).isoformat(timespec='seconds')

def money(value, positive=False):
    try:
        d = Decimal(str(value).replace(' ', '').replace(',', '.'))
        if not d.is_finite() or d < 0 or (positive and d == 0) or d.as_tuple().exponent < -2 or d > Decimal('1000000000000'):
            raise ValueError()
        return int(d * 100)
    except (InvalidOperation, ValueError):
        raise ValueError('amount') from None

def exchange_rate(value):
    try:
        rate = Decimal(str(value).replace(' ', '').replace(',', '.'))
        if not rate.is_finite() or rate <= 0 or rate > 1000000 or rate.as_tuple().exponent < -2:
            raise ValueError()
        return rate
    except (InvalidOperation, ValueError):
        raise ValueError('exchange_rate') from None

parse_exchange_rate = exchange_rate

def fmt(value):
    return f'{Decimal(value) / 100:,.2f}'.replace(',', ' ')

def integer(value):
    try:
        x = int(value)
        if not 0 < x <= 1000000:
            raise ValueError()
        return x
    except (ValueError, TypeError):
        raise ValueError('quantity') from None

def parse_item_lines(text):
    """Parse ID, quantity and unit price without dropping negative signs."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if '|' in line:
            separator = r'[ \t]*\|[ \t]*'
            price = r'[0-9]+(?:[ \t\u00a0\u202f][0-9]{3})*(?:[.,][0-9]{1,2})?'
        elif any(char in line for char in '-–—'):
            separator = r'[ \t]*[-–—][ \t]*'
            price = r'[0-9]+(?:[ \t\u00a0\u202f][0-9]{3})*(?:[.,][0-9]{1,2})?'
        else:
            separator = r'[ \t\u00a0\u202f]+'
            price = r'[0-9]+(?:[.,][0-9]{1,2})?'
        match = re.fullmatch(
            r'([0-9]+)' + separator + r'([0-9]+)' + separator
            + '(' + price + ')', line
        )
        if not match:
            raise ValueError('items')
        product, qty, price_text = match.groups()
        price_text = re.sub(r'[ \t\u00a0\u202f]', '', price_text)
        money(price_text)
        rows.append(dict(product=integer(product), qty=integer(qty),
                         price=price_text, discount=0))
    if not rows or len(rows) > 50:
        raise ValueError('items')
    return rows

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('director','employee')), name TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'uz', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(user_id INTEGER PRIMARY KEY REFERENCES users(id), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, note TEXT NOT NULL, owner INTEGER NOT NULL REFERENCES users(id), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0), photo TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS stock(product INTEGER NOT NULL REFERENCES products(id), point INTEGER NOT NULL REFERENCES points(id), qty INTEGER NOT NULL CHECK(qty>=0), PRIMARY KEY(product,point));
CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product INTEGER NOT NULL REFERENCES products(id), point INTEGER NOT NULL REFERENCES points(id), qty INTEGER NOT NULL, kind TEXT NOT NULL, actor INTEGER NOT NULL REFERENCES users(id), note TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), point INTEGER NOT NULL REFERENCES points(id), actor INTEGER NOT NULL REFERENCES users(id), total INTEGER NOT NULL CHECK(total>=0), paid INTEGER NOT NULL CHECK(paid>=0 AND paid<=total), payment TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY, sale INTEGER NOT NULL REFERENCES sales(id), product INTEGER NOT NULL REFERENCES products(id), name TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty>0), price INTEGER NOT NULL CHECK(price>=0), discount INTEGER NOT NULL CHECK(discount BETWEEN 0 AND 100));
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, sale INTEGER NOT NULL REFERENCES sales(id), amount INTEGER NOT NULL CHECK(amount>0), method TEXT NOT NULL, actor INTEGER NOT NULL REFERENCES users(id), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), actor INTEGER NOT NULL REFERENCES users(id), total INTEGER NOT NULL, terms TEXT NOT NULL, lang TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quote_items(id INTEGER PRIMARY KEY, quote INTEGER NOT NULL REFERENCES quotes(id), product INTEGER NOT NULL REFERENCES products(id), name TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty>0), price INTEGER NOT NULL CHECK(price>=0), discount INTEGER NOT NULL CHECK(discount BETWEEN 0 AND 100));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), actor INTEGER NOT NULL REFERENCES users(id), due TEXT NOT NULL, note TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', notified INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), actor INTEGER NOT NULL REFERENCES users(id), result TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL REFERENCES users(id), started TEXT NOT NULL, ended TEXT, report TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_shift ON shifts(actor) WHERE ended IS NULL;
CREATE TABLE IF NOT EXISTS fines(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL REFERENCES users(id), amount INTEGER NOT NULL CHECK(amount>0), reason TEXT NOT NULL, approved_by INTEGER NOT NULL REFERENCES users(id), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), sale INTEGER REFERENCES sales(id), actor INTEGER NOT NULL REFERENCES users(id), driver TEXT NOT NULL, address TEXT NOT NULL, fee INTEGER NOT NULL CHECK(fee>=0), paid INTEGER NOT NULL CHECK(paid>=0 AND paid<=fee), status TEXT NOT NULL DEFAULT 'new', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL, action TEXT NOT NULL, ref INTEGER, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS refunds(id INTEGER PRIMARY KEY, sale INTEGER UNIQUE NOT NULL REFERENCES sales(id), amount INTEGER NOT NULL CHECK(amount>=0), method TEXT NOT NULL, actor INTEGER NOT NULL REFERENCES users(id), reason TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stock_limits(product INTEGER NOT NULL REFERENCES products(id), point INTEGER NOT NULL REFERENCES points(id), minimum INTEGER NOT NULL CHECK(minimum>=0), alerted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(product,point));
CREATE TABLE IF NOT EXISTS ui_views(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS staff_access(user_id INTEGER PRIMARY KEY REFERENCES users(id), active INTEGER NOT NULL CHECK(active IN (0,1)));
CREATE TABLE IF NOT EXISTS staff_invites(id INTEGER PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, label TEXT NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', joined_by INTEGER REFERENCES users(id));
'''

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        # Additive migration: old quotes retain their original items and totals.
        columns={r[1] for r in self.db.execute('PRAGMA table_info(quotes)')}
        for name in ('payment','fulfillment'):
            if name not in columns:
                self.db.execute(f"ALTER TABLE quotes ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        for table, fields in {
            'staff_access':{'position_id':'INTEGER REFERENCES positions(id)','managed_role':'TEXT'},
            'staff_invites':{'position_id':'INTEGER REFERENCES positions(id)','role':"TEXT NOT NULL DEFAULT 'employee'"},
            'products':{'brand':"TEXT NOT NULL DEFAULT ''",'size':"TEXT NOT NULL DEFAULT ''",'catalog_sku':'TEXT','price_pending':'INTEGER NOT NULL DEFAULT 0'},
            'sales':{'status':"TEXT NOT NULL DEFAULT 'active'",'debt_due':"TEXT NOT NULL DEFAULT ''",'cancel_reason':"TEXT NOT NULL DEFAULT ''",'cancelled_by':'INTEGER','cancelled_at':"TEXT NOT NULL DEFAULT ''"},
        }.items():
            existing={r[1] for r in self.db.execute(f'PRAGMA table_info({table})')}
            for name,definition in fields.items():
                if name not in existing:self.db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        for table in ('products','sales','payments','refunds','fines','deliveries','quotes'):
            columns = {r[1] for r in self.db.execute(f'PRAGMA table_info({table})')}
            if 'currency' not in columns:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN currency TEXT NOT NULL DEFAULT 'UZS'")
                if table == 'products':
                    self.db.execute("UPDATE products SET price_pending=1")
                    self.db.execute('DELETE FROM sessions')
                    self.db.execute('DELETE FROM ui_views')
        image_columns = {r[1] for r in self.db.execute('PRAGMA table_info(quote_items)')}
        if 'photo' not in image_columns:
            self.db.execute("ALTER TABLE quote_items ADD COLUMN photo TEXT NOT NULL DEFAULT ''")
            self.db.execute("UPDATE quote_items SET photo=COALESCE((SELECT photo FROM products WHERE products.id=quote_items.product),'')")
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(quotes)')}
        if 'exchange_rate' not in columns:
            self.db.execute("ALTER TABLE quotes ADD COLUMN exchange_rate TEXT NOT NULL DEFAULT ''")
        if 'source_total_usd' not in columns:
            self.db.execute('ALTER TABLE quotes ADD COLUMN source_total_usd INTEGER')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS products_catalog_sku ON products(catalog_sku) WHERE catalog_sku IS NOT NULL')
        self.db.commit()
        if self.db.execute('PRAGMA journal_mode').fetchone()[0]!='wal':
            self.db.execute('PRAGMA journal_mode=WAL')
        self.db.commit()

    def rows(self, sql, params=()):
        return [dict(r) for r in self.db.execute(sql, params)]

    def one(self, table, key):
        if table not in {'users','clients','points','products','sales','quotes','tasks','deliveries'}:
            raise ValueError('table')
        r = self.db.execute(f'SELECT * FROM {table} WHERE id=?', (key,)).fetchone()
        if not r:
            raise ValueError('missing')
        return dict(r)

    def add(self, table, **data):
        if table in {'products','sales','payments','refunds','fines','deliveries'}:
            data.setdefault('currency', self.one('sales',data['sale'])['currency'] if table in {'payments','refunds'} else 'USD')
        keys = ','.join(data)
        marks = ','.join('?' for _ in data)
        return self.db.execute(f'INSERT INTO {table} ({keys}) VALUES ({marks})', tuple(data.values())).lastrowid

    def user(self, uid):
        u = self.one('users', uid)
        if not u['active']:
            raise PermissionError()
        return u

    def director(self, uid):
        if self.user(uid)['role'] != 'director':
            raise PermissionError()

    def own(self, uid, row):
        if row['actor'] != uid:
            self.director(uid)

    def log(self, uid, action, ref=None):
        self.add('audit', actor=uid, action=action, ref=ref, created=now())

    def configure(self, directors, employees):
        if len(directors)>3 or set(directors)&set(employees) or not directors:
            raise ValueError('Configure 1-3 directors and distinct employees')
        with self.db:
            self.db.execute('UPDATE users SET active=0')
            for role, ids in [('director',directors),('employee',employees)]:
                for uid in ids:
                    self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET role=excluded.role,active=1',(uid,role,str(uid)))
            # Panel-managed access survives either service restarting. An explicit
            # panel suspension also overrides legacy EMPLOYEE_IDS entries.
            self.db.execute("UPDATE users SET active=(SELECT active FROM staff_access WHERE user_id=users.id),role=COALESCE((SELECT managed_role FROM staff_access WHERE user_id=users.id),role) WHERE id IN (SELECT user_id FROM staff_access)")

    def product(self, uid, name, price, photo=None):
        self.director(uid)
        ref = self.add('products',name=name,price=money(price),photo=photo)
        self.log(uid,'product',ref)
        return ref

    def edit_product(self,uid,product,name,brand,size,price,photo=None):
        self.director(uid);old=self.one('products',product)
        self.db.execute("UPDATE products SET name=?,brand=?,size=?,price=?,photo=?,price_pending=0,currency='USD' WHERE id=?",
            (name or old['name'],brand,size,money(price),photo if photo is not None else old['photo'],product))
        self.log(uid,'product_edit',product)
        return product

    def set_minimum(self,uid,product,point,minimum):
        self.director(uid);self.one('products',product);self.one('points',point)
        try:minimum=int(minimum)
        except (TypeError,ValueError):raise ValueError('quantity') from None
        if not 0<=minimum<=1000000:raise ValueError('quantity')
        self.db.execute('INSERT INTO stock_limits VALUES(?,?,?,0) ON CONFLICT(product,point) DO UPDATE SET minimum=excluded.minimum,alerted=0',(product,point,minimum))
        self.log(uid,'stock_minimum',product)
        return product

    def rearm_stock(self,product,point):
        self.db.execute('UPDATE stock_limits SET alerted=0 WHERE product=? AND point=? AND minimum<(SELECT qty FROM stock WHERE product=? AND point=?)',(product,point,product,point))

    def set_debt_due(self,uid,sale,debt_due):
        self.user(uid);row=self.one('sales',sale);self.own(uid,row)
        if row['status']!='active' or row['paid']>=row['total']:raise ValueError('no_debt')
        if debt_due:
            try:debt_due=datetime.strptime(debt_due,'%Y-%m-%d').date().isoformat()
            except ValueError:raise ValueError('date') from None
        self.db.execute('UPDATE sales SET debt_due=? WHERE id=?',(debt_due,sale))
        self.log(uid,'debt_due',sale)
        return sale

    def debts(self,uid,overdue=False):
        user=self.user(uid)
        scope='' if user['role']=='director' else ' AND s.actor=?'
        params=[] if not scope else [uid]
        date=''
        if overdue:
            date=" AND s.debt_due<>'' AND s.debt_due<?";params.append(now()[:10])
        return self.rows("SELECT s.*,c.name client_name,c.phone,u.name employee_name,s.total-s.paid debt FROM sales s JOIN clients c ON c.id=s.client JOIN users u ON u.id=s.actor WHERE s.status='active' AND s.paid<s.total"+scope+date+' ORDER BY s.debt_due,s.id',params)

    def cancel_sale(self,uid,sale,reason,refund_confirmed=False,expected_paid=None):
        self.director(uid);row=self.one('sales',sale)
        if row['status']!='active':raise ValueError('sale_cancelled')
        if expected_paid is not None and row['paid']!=expected_paid:raise ValueError('sale_changed')
        if not reason.strip():raise ValueError('reason')
        if row['paid'] and not refund_confirmed:raise ValueError('refund_required')
        cur=self.db.execute("UPDATE sales SET status='cancelled',cancel_reason=?,cancelled_by=?,cancelled_at=? WHERE id=? AND status='active' AND paid=?",(reason,uid,now(),sale,row['paid']))
        if not cur.rowcount:raise ValueError('sale_changed')
        for item in self.rows('SELECT product,SUM(qty) qty FROM sale_items WHERE sale=? GROUP BY product',(sale,)):
            self.db.execute('INSERT INTO stock VALUES(?,?,?) ON CONFLICT(product,point) DO UPDATE SET qty=qty+excluded.qty',(item['product'],row['point'],item['qty']))
            self.add('movements',product=item['product'],point=row['point'],qty=item['qty'],kind='sale_cancel',actor=uid,note=f'#{sale}: {reason}',created=now())
            self.rearm_stock(item['product'],row['point'])
        if row['paid']:
            # A separate reversal preserves every original receipt and its date.
            self.add('refunds',sale=sale,amount=row['paid'],method='refund',actor=uid,reason=reason,created=now())
        self.log(uid,'sale_cancel',sale)
        return sale

    def move(self, uid, product, point, qty, kind, note):
        self.user(uid)
        self.one('products',product); self.one('points',point)
        if kind not in {'in','return','writeoff'}:
            raise ValueError('kind')
        if kind == 'writeoff':
            self.director(uid)
        qty=integer(qty) * (-1 if kind=='writeoff' else 1)
        self.db.execute('INSERT OR IGNORE INTO stock VALUES(?,?,0)',(product,point))
        cur=self.db.execute('UPDATE stock SET qty=qty+? WHERE product=? AND point=? AND qty+?>=0',(qty,product,point,qty))
        if not cur.rowcount:
            raise ValueError('stock')
        self.rearm_stock(product,point)
        ref=self.add('movements',product=product,point=point,qty=qty,kind=kind,actor=uid,note=note,created=now())
        self.log(uid,kind,ref)
        return ref

    def opening_stock(self,uid,product,point,qty,note=''):
        self.director(uid);self.one('products',product);self.one('points',point)
        if isinstance(qty,bool) or not re.fullmatch(r'\d+',str(qty)):
            raise ValueError('quantity')
        qty=int(qty)
        if not 0<=qty<=1000000:raise ValueError('quantity')
        if self.db.execute('SELECT 1 FROM stock WHERE product=? AND point=?',(product,point)).fetchone():
            raise ValueError('stock_exists')
        self.db.execute('INSERT INTO stock VALUES(?,?,?)',(product,point,qty))
        ref=self.add('movements',product=product,point=point,qty=qty,kind='opening',actor=uid,note=note,created=now())
        self.log(uid,'opening_stock',ref)
        return ref

    def client(self, uid, name, phone, address, note):
        self.user(uid)
        ref=self.add('clients', name=name,phone=phone,address=address,note=note,owner=uid,created=now())
        self.log(uid,'client',ref)
        return ref

    def items(self, items):
        result=[]
        for i in items:
            p=self.one('products',integer(i['product']))
            if not p['active']:
                raise ValueError('missing')
            qty=integer(i['qty']); price=money(i['price'])
            discount=int(i.get('discount',0))
            if discount != 0:
                raise ValueError('discount_removed')
            total=int((Decimal(price)*qty*(100-discount)/100).quantize(Decimal('1')))
            if total > 10**16:
                raise ValueError('amount')
            result.append(dict(product=p['id'],name=p['name'],qty=qty,price=price,discount=discount,total=total))
        if not result or len(result)>50:
            raise ValueError('items')
        return result

    def order(self, uid, client, items, point=None, paid='0', payment='', terms='', quote=False, fulfillment='', exchange_rate=None):
        self.user(uid); self.one('clients',client)
        lines=self.items(items); total=sum(i['total'] for i in lines)
        if total > 10**16:
            raise ValueError('amount')
        if quote:
            rate = parse_exchange_rate(exchange_rate)
            source_total = total if rate is not None else None
            if rate is not None:
                for item in lines:
                    item['price'] = int((Decimal(item['price'])*rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    item['total'] = item['price']*item['qty']
                total = sum(i['total'] for i in lines)
                if total > 10**16: raise ValueError('amount')
            payment=normalize_payment(payment) if payment else ''
            fulfillment=normalize_fulfillment(fulfillment) if fulfillment else ''
            ref=self.add('quotes',client=client,actor=uid,total=total,terms=terms,lang=self.user(uid)['lang'],created=now(),payment=payment,fulfillment=fulfillment,currency='UZS',exchange_rate=str(rate) if rate is not None else '',source_total_usd=source_total)
            for item in lines:
                self.add('quote_items',quote=ref,photo=self.one('products',item['product'])['photo'] or '',**{k:v for k,v in item.items() if k!='total'})
            self.log(uid,'quote',ref)
            return ref
        self.one('points',point)
        payment=normalize_payment(payment)
        paid=money(paid)
        if paid>total:
            raise ValueError('paid')
        # All changes must run in the caller's transaction. Any failed line rolls everything back.
        ref=self.add('sales',client=client,point=point,actor=uid,total=total,paid=paid,payment=payment,created=now())
        for item in lines:
            cur=self.db.execute('UPDATE stock SET qty=qty-? WHERE product=? AND point=? AND qty>=?',(item['qty'],item['product'],point,item['qty']))
            if not cur.rowcount:
                raise ValueError('stock')
            self.add('sale_items',sale=ref,**{k:v for k,v in item.items() if k!='total'})
            self.add('movements',product=item['product'],point=point,qty=-item['qty'],kind='sale',actor=uid,note=f'#{ref}',created=now())
        if paid:
            self.add('payments',sale=ref,amount=paid,method=payment,actor=uid,created=now())
        self.log(uid,'sale',ref)
        return ref

    def quote_options(self,uid,ref,payment,fulfillment):
        self.user(uid);self.own(uid,self.one('quotes',ref))
        payment=normalize_payment(payment);fulfillment=normalize_fulfillment(fulfillment)
        self.db.execute('UPDATE quotes SET payment=?,fulfillment=? WHERE id=?',(payment,fulfillment,ref))
        self.log(uid,'quote_options',ref)
        return ref

    def payment(self,uid,sale,amount,method):
        self.user(uid)
        if self.one('sales',sale)['status']!='active':raise ValueError('sale_cancelled')
        method=normalize_payment(method)
        amount=money(amount,True)
        cur=self.db.execute("UPDATE sales SET paid=paid+? WHERE id=? AND status='active' AND paid+?<=total",(amount,sale,amount))
        if not cur.rowcount:
            raise ValueError('paid')
        ref=self.add('payments',sale=sale,amount=amount,method=method,actor=uid,created=now())
        self.log(uid,'payment',ref)
        return ref

    def start(self,uid):
        self.user(uid)
        if self.db.execute('SELECT 1 FROM shifts WHERE actor=? AND ended IS NULL',(uid,)).fetchone():
            raise ValueError('shift_open')
        ref=self.add('shifts',actor=uid,started=now())
        self.log(uid,'shift_start',ref)
        return ref

    def end(self,uid,report):
        self.user(uid)
        cur=self.db.execute('UPDATE shifts SET ended=?,report=? WHERE actor=? AND ended IS NULL',(now(),report,uid))
        if not cur.rowcount:
            raise ValueError('shift_closed')
        self.log(uid,'shift_end')

    def task(self,uid,client,assignee,due,note):
        self.user(uid); self.one('clients',client); self.user(assignee)
        if uid!=assignee:
            self.director(uid)
        try:
            date=datetime.strptime(due,'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        except ValueError:
            raise ValueError('date') from None
        if date <= datetime.now(TZ):
            raise ValueError('date')
        ref=self.add('tasks',client=client,actor=assignee,due=date.isoformat(timespec='seconds'),note=note,created=now())
        self.log(uid,'task',ref)
        return ref

    def complete_task(self,uid,ref):
        self.own(uid,self.one('tasks',ref))
        self.db.execute("UPDATE tasks SET status='done' WHERE id=?",(ref,))
        self.log(uid,'task_done',ref)

    def fine(self,uid,employee,amount,reason):
        self.director(uid); self.user(employee)
        ref=self.add('fines',actor=employee,amount=money(amount,True),reason=reason,approved_by=uid,created=now())
        self.log(uid,'fine',ref)
        return ref

    def call(self,uid,client,result,note):
        self.user(uid); self.one('clients',client)
        ref=self.add('calls',client=client,actor=uid,result=result,note=note,created=now())
        self.log(uid,'call',ref)
        return ref

    def delivery(self,uid,client,sale,driver,address,fee,paid):
        self.user(uid); self.one('clients',client)
        if sale:
            s=self.one('sales',sale)
            if s['client']!=client:
                raise ValueError('client')
        fee=money(fee); paid=money(paid)
        if paid>fee:
            raise ValueError('paid')
        ref=self.add('deliveries',client=client,sale=sale,actor=uid,driver=driver,address=address,fee=fee,paid=paid,created=now())
        self.log(uid,'delivery',ref)
        return ref

    def delivery_status(self,uid,ref,status):
        row=self.one('deliveries',ref); self.own(uid,row)
        if status not in {'new','on_way','delivered','cancelled'}:
            raise ValueError('status')
        self.db.execute('UPDATE deliveries SET status=? WHERE id=?',(status,ref))
        self.log(uid,'delivery_status',ref)

    def stock(self,uid):
        self.user(uid)
        return self.rows('SELECT p.id,p.name,p.brand,p.size,p.price,p.price_pending,p.currency,p.catalog_sku,p.photo,t.id point_id,t.name point,COALESCE(s.qty,0) qty,s.qty IS NOT NULL stock_set FROM products p LEFT JOIN points t ON 1=1 LEFT JOIN stock s ON s.product=p.id AND s.point=t.id WHERE p.active=1 ORDER BY t.id,p.id')

    def report(self,uid,start,end):
        self.user(uid)
        try:
            a=datetime.strptime(start,'%Y-%m-%d'); b=datetime.strptime(end,'%Y-%m-%d')
            if a>b: raise ValueError()
        except ValueError:
            raise ValueError('date') from None
        scope='' if self.user(uid)['role']=='director' else ' AND actor=?'
        params=(start,end) if not scope else (start,end,uid)
        result={}
        for table,field in [('sales','created'),('payments','created'),('refunds','created'),('calls','created'),('deliveries','created'),('shifts','started'),('fines','created'),('quotes','created')]:
            result[table]=self.rows(f'SELECT * FROM {table} WHERE substr({field},1,10) BETWEEN ? AND ?'+scope+' ORDER BY id',params)
        result['sale_items']=self.rows('SELECT i.*,s.actor,s.client,s.point,s.created,s.status,s.currency FROM sale_items i JOIN sales s ON i.sale=s.id WHERE substr(s.created,1,10) BETWEEN ? AND ?'+('' if not scope else ' AND s.actor=?')+' ORDER BY i.sale,i.id',params)
        result['tasks']=self.rows("SELECT * FROM tasks WHERE status='open'"+('' if not scope else ' AND actor=?'),() if not scope else (uid,))
        result['movements']=self.rows('SELECT m.id,m.created,p.name,p.brand,p.size,t.name warehouse_name,m.qty,m.kind,m.actor,m.note FROM movements m JOIN products p ON p.id=m.product JOIN points t ON t.id=m.point WHERE substr(m.created,1,10) BETWEEN ? AND ?'+('' if not scope else ' AND m.actor=?')+' ORDER BY m.id',params)
        result['product_events']=self.rows("SELECT a.created,p.name,p.brand,p.size,a.action,a.actor FROM audit a JOIN products p ON p.id=a.ref WHERE a.action IN ('product','product_edit') AND substr(a.created,1,10) BETWEEN ? AND ?"+('' if not scope else ' AND a.actor=?')+' ORDER BY a.id',params)
        return result

    def inventory_report(self,uid):
        stamp=now();rows=[];warehouses={}
        for r in self.stock(uid):
            if r['point_id'] is None:continue
            unknown=bool(r['catalog_sku'] and not r['stock_set'])
            row={k:r[k] for k in ('id','name','brand','size','point')}
            row.update(currency=r['currency'],qty=None if unknown else r['qty'],price=None if r['price_pending'] else r['price'],stock_status='unknown' if unknown else 'known',as_of=stamp)
            row['stock_value']=None if unknown or r['price_pending'] else r['qty']*r['price']
            rows.append(row)
            w=warehouses.setdefault((r['point_id'],r['currency']),{'warehouse_name':r['point'],'currency':r['currency'],'qty':0,'stock_value':0,'unknown_stock':0,'unknown_price':0,'as_of':stamp})
            if unknown:w['unknown_stock']+=1
            else:w['qty']+=r['qty']
            if not unknown and r['price_pending'] and r['qty']:w['unknown_price']+=1
            if row['stock_value'] is not None:w['stock_value']+=row['stock_value']
        return {'stock':rows,'warehouses':list(warehouses.values())}

    def client_card(self,uid,ref):
        self.user(uid)
        result={'client':[self.one('clients',ref)]}
        for table in ('sales','quotes','calls','tasks','deliveries'):
            result[table]=self.rows(f'SELECT * FROM {table} WHERE client=? ORDER BY id DESC',(ref,))
        result['refunds']=self.rows('SELECT r.* FROM refunds r JOIN sales s ON s.id=r.sale WHERE s.client=? ORDER BY r.id DESC',(ref,))
        return result


def csv_report(sections):
    out=io.StringIO(newline='')
    w=csv.writer(out)
    for name,rows in sections.items():
        w.writerow([name])
        if rows:
            fields=list(rows[0]); w.writerow(fields)
            for r in rows:
                # Prevent formulas when opening user-controlled text in Excel.
                values=[]
                for k in fields:
                    val=r[k]
                    if isinstance(val,str) and val.lstrip().startswith(('=','+','-','@')):
                        val="'"+val
                    values.append(val)
                w.writerow(values)
        w.writerow([])
    return out.getvalue().encode('utf-8-sig')
