"""Additive accounting and receipt provenance. Callers own the transaction.

Quantities and money use integers. Unattributed stock is consumed before FIFO
receipts; neither legacy stock nor legacy sales are assigned a supplier.
"""
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
import json
import re


@contextmanager
def transaction(store):
    # Starting an outer transaction keeps RELEASE from committing a caller's work.
    if not store.db.in_transaction:
        store.db.execute('BEGIN IMMEDIATE')
    store.db.execute('SAVEPOINT accounting_write')
    try:
        yield
    except Exception:
        store.db.execute('ROLLBACK TO accounting_write')
        store.db.execute('RELEASE accounting_write')
        raise
    else:
        store.db.execute('RELEASE accounting_write')


def atomic(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with transaction(self):
            return method(self, *args, **kwargs)
    return wrapped


def quantity(value, zero=False):
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError('quantity')
    value = int(value)
    if not (0 if zero else 1) <= value <= 1000000:
        raise ValueError('quantity')
    return value


def valid_currency(value):
    if value not in ('USD', 'UZS'):
        raise ValueError('currency')
    return value


def accounting_date(value=None):
    from core import now
    value = now()[:10] if value is None else value
    try:
        if not isinstance(value, str) or datetime.strptime(value, '%Y-%m-%d').date().isoformat() != value:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('date') from None
    return value


def clean_note(value, required=False, limit=1500):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError('text')
    return value.strip()


TABLES = (
    '''CREATE TABLE IF NOT EXISTS suppliers(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
        note TEXT NOT NULL, actor INTEGER NOT NULL REFERENCES users(id), created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL REFERENCES suppliers(id),
        product INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL CHECK(qty>0),
        cost INTEGER NOT NULL CHECK(cost>=0), currency TEXT NOT NULL CHECK(currency IN ('USD','UZS')),
        actor INTEGER NOT NULL REFERENCES users(id), note TEXT NOT NULL, date TEXT NOT NULL, created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS inventory_lots(
        id INTEGER PRIMARY KEY, receipt INTEGER REFERENCES receipts(id),
        product INTEGER NOT NULL REFERENCES products(id), point INTEGER NOT NULL REFERENCES points(id),
        qty INTEGER NOT NULL CHECK(qty>=0), created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS sale_allocations(
        item INTEGER NOT NULL REFERENCES sale_items(id), lot INTEGER NOT NULL REFERENCES inventory_lots(id),
        qty INTEGER NOT NULL CHECK(qty>0), PRIMARY KEY(item,lot))''',
    '''CREATE TABLE IF NOT EXISTS manager_entries(
        id INTEGER PRIMARY KEY, manager INTEGER NOT NULL REFERENCES users(id),
        kind TEXT NOT NULL CHECK(kind IN ('fund','expense','return')),
        amount INTEGER NOT NULL CHECK(amount>0), currency TEXT NOT NULL CHECK(currency IN ('USD','UZS')),
        actor INTEGER NOT NULL REFERENCES users(id), note TEXT NOT NULL, date TEXT NOT NULL, created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS supplier_entries(
        id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL REFERENCES suppliers(id),
        kind TEXT NOT NULL CHECK(kind IN ('receipt','payment','return')),
        amount INTEGER NOT NULL CHECK(amount>=0), currency TEXT NOT NULL CHECK(currency IN ('USD','UZS')),
        method TEXT NOT NULL DEFAULT '',
        receipt INTEGER REFERENCES receipts(id), lot INTEGER REFERENCES inventory_lots(id),
        qty INTEGER, manager_entry INTEGER UNIQUE REFERENCES manager_entries(id),
        actor INTEGER NOT NULL REFERENCES users(id), note TEXT NOT NULL, date TEXT NOT NULL, created TEXT NOT NULL)''',
    'CREATE INDEX IF NOT EXISTS lots_stock ON inventory_lots(product,point,id)',
    'CREATE INDEX IF NOT EXISTS supplier_ledger ON supplier_entries(supplier,currency,date)',
    'CREATE INDEX IF NOT EXISTS manager_ledger ON manager_entries(manager,currency,date)',
)


def migrate(store):
    """Idempotent, transactional migration. No existing commercial data changes."""
    from core import now
    with store.db:
        with transaction(store):
            for sql in TABLES:
                store.db.execute(sql)
            for table, column, definition in (
                ('points', 'kind', "TEXT NOT NULL DEFAULT 'sklad' CHECK(kind IN ('sklad','vitrina'))"),
                ('sale_items', 'point', 'INTEGER REFERENCES points(id)'),
                ('sale_items', 'location_kind', "TEXT CHECK(location_kind IN ('sklad','vitrina'))"),
                ('supplier_entries', 'method', "TEXT NOT NULL DEFAULT ''"),
            ):
                if column not in {r[1] for r in store.db.execute(f'PRAGMA table_info({table})')}:
                    store.db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            if not store.db.execute("SELECT 1 FROM meta WHERE key='accounting_v1'").fetchone():
                store.db.execute('INSERT INTO inventory_lots(receipt,product,point,qty,created) SELECT NULL,product,point,qty,? FROM stock WHERE qty>0', (now(),))
                store.db.execute("INSERT INTO meta(key,value) VALUES('accounting_v1',?)", (now(),))


class Accounting:
    def supplier_row(self, ref):
        rows = self.rows('SELECT * FROM suppliers WHERE id=?', (quantity(ref),))
        if not rows:
            raise ValueError('missing')
        return rows[0]

    @atomic
    def supplier_save(self, uid, name, phone='', note='', supplier=None):
        from core import now
        self.director(uid)
        data = dict(name=clean_note(name, True, 150), phone=clean_note(phone, False, 100), note=clean_note(note))
        if supplier is None:
            ref = self.add('suppliers', **data, actor=uid, created=now())
            self.log(uid, 'supplier_create', ref)
        else:
            old = self.supplier_row(supplier)
            ref = old['id']
            self.db.execute('UPDATE suppliers SET name=?,phone=?,note=? WHERE id=?', (*data.values(), ref))
            # Retain old and new values in the existing immutable audit stream.
            self.log(uid, 'supplier_edit:' + json.dumps({'before':old, 'after':data}, ensure_ascii=False, sort_keys=True), ref)
        return ref

    def suppliers(self, uid, for_receipt=False):
        self.user(uid)
        if for_receipt:
            return self.rows('SELECT id,name FROM suppliers ORDER BY name,id')
        self.director(uid)
        return {'suppliers':self.rows('SELECT * FROM suppliers ORDER BY name,id'), 'balances':self.rows("SELECT supplier,currency,SUM(CASE WHEN kind='receipt' THEN amount ELSE -amount END) balance FROM supplier_entries GROUP BY supplier,currency")}

    @atomic
    def point_kind(self, uid, point, kind):
        self.director(uid)
        old = self.one('points', point)
        if kind not in ('sklad', 'vitrina'):
            raise ValueError('point_kind')
        self.db.execute('UPDATE points SET kind=? WHERE id=?', (kind, point))
        self.log(uid, 'point_kind:' + old['kind'] + ':' + kind, point)
        return point

    def _unassigned_lot(self, product, point, qty):
        from core import now
        if qty:
            return self.add('inventory_lots', receipt=None, product=product, point=point, qty=qty, created=now())

    def _consume_lots(self, product, point, qty, item=None):
        remaining = qty
        lots = self.rows('SELECT * FROM inventory_lots WHERE product=? AND point=? AND qty>0 ORDER BY receipt IS NOT NULL,receipt,id', (product, point))
        for lot in lots:
            take = min(remaining, lot['qty'])
            self.db.execute('UPDATE inventory_lots SET qty=qty-? WHERE id=?', (take, lot['id']))
            if item:
                self.add('sale_allocations', item=item, lot=lot['id'], qty=take)
            remaining -= take
            if not remaining:
                return
        raise ValueError('stock_provenance')

    @atomic
    def receive(self, uid, product, supplier, cost, allocations, note='', date=None, currency='USD', payments=None, manager=None):
        from core import now, money
        user=self.user(uid)
        self.one('products', quantity(product))
        self.supplier_row(supplier)
        cost = money(cost)
        currency = valid_currency(currency)
        stamp, note = accounting_date(date), clean_note(note)
        if manager is None and user['role']=='employee':
            manager=uid
        elif manager is not None:
            self._manager_access(uid,manager)
        if not isinstance(allocations, list) or not 1 <= len(allocations) <= 2:
            raise ValueError('allocations')
        clean = []
        for allocation in allocations:
            if not isinstance(allocation, dict):
                raise ValueError('allocations')
            point, qty = quantity(allocation.get('point')), quantity(allocation.get('qty'))
            self.one('points', point)
            clean.append((point, qty))
        if len({p for p, q in clean}) != len(clean) or sum(q for p, q in clean) > 1000000:
            raise ValueError('allocations')
        total=cost*sum(q for p,q in clean)
        if total>10**16:
            raise ValueError('amount')
        if payments is None:payments=[]
        if not isinstance(payments,list) or len(payments)>3:raise ValueError('payment')
        clean_payments=[];seen=set();paid_total=0
        for payment in payments:
            if not isinstance(payment,dict):raise ValueError('payment')
            method=payment.get('method')
            if method not in ('cash','transfer','card') or method in seen:raise ValueError('payment')
            seen.add(method)
            amount=money(payment.get('amount','0'))
            if amount:
                clean_payments.append((method,amount));paid_total+=amount
        if paid_total>total:raise ValueError('paid')
        ref = self.add('receipts', supplier=supplier, product=product, qty=sum(q for p, q in clean), cost=cost, currency=currency, actor=uid, note=note, date=stamp, created=now())
        for point, qty in clean:
            self.add('inventory_lots', receipt=ref, product=product, point=point, qty=qty, created=now())
            self.db.execute('INSERT INTO stock(product,point,qty) VALUES(?,?,?) ON CONFLICT(product,point) DO UPDATE SET qty=qty+excluded.qty', (product, point, qty))
            self.add('movements', product=product, point=point, qty=qty, kind='supplier_income', actor=uid, note=f'#{ref}: {note}', created=now())
            self.rearm_stock(product, point)
        self.add('supplier_entries', supplier=supplier, kind='receipt', amount=total, currency=currency, receipt=ref, actor=uid, note=note, date=stamp, created=now())
        if paid_total:
            from core import fmt
            for method,amount in clean_payments:
                manager_entry=None
                payment_note=note or f'Kirim #{ref}'
                if manager is not None:
                    manager_entry=self.manager_record(uid,manager,'expense',fmt(amount).replace(' ',''),payment_note,stamp,currency)
                self.add('supplier_entries',supplier=supplier,kind='payment',amount=amount,currency=currency,method=method,receipt=ref,manager_entry=manager_entry,actor=uid,note=payment_note,date=stamp,created=now())
        self.log(uid, 'supplier_income', ref)
        return ref

    def _manager_access(self, uid, manager):
        self.user(uid)
        target = self.one('users', manager)
        if target['role'] != 'employee':
            raise ValueError('manager')
        if uid != manager:
            self.director(uid)

    @atomic
    def manager_record(self, uid, manager, kind, amount, note='', date=None, currency='USD'):
        from core import now, money
        self._manager_access(uid, manager)
        if kind not in ('fund', 'expense', 'return'):
            raise ValueError('kind')
        if kind == 'fund':
            self.director(uid)
            self.user(manager)
        ref = self.add('manager_entries', manager=manager, kind=kind, amount=money(amount, True), currency=valid_currency(currency), actor=uid, note=clean_note(note), date=accounting_date(date), created=now())
        self.log(uid, 'manager_' + kind, ref)
        return ref

    def manager_account(self, uid, manager=None):
        user = self.user(uid)
        if manager is not None:
            self._manager_access(uid, manager)
        elif user['role'] != 'director':
            manager = uid
        scope = ' WHERE e.manager=?' if manager is not None else ''
        params = (manager,) if manager is not None else ()
        entries = self.rows('SELECT e.*,u.name manager_name,a.name actor_name FROM manager_entries e JOIN users u ON u.id=e.manager JOIN users a ON a.id=e.actor'+scope+' ORDER BY e.id DESC', params)
        balances = self.rows("SELECT e.manager,u.name manager_name,e.currency,SUM(CASE WHEN e.kind='fund' THEN e.amount ELSE 0 END) given,SUM(CASE WHEN e.kind='expense' THEN e.amount ELSE 0 END) expenses,SUM(CASE WHEN e.kind='return' THEN e.amount ELSE 0 END) returned,SUM(CASE WHEN e.kind='fund' THEN e.amount ELSE -e.amount END) balance FROM manager_entries e JOIN users u ON u.id=e.manager"+scope+' GROUP BY e.manager,e.currency', params)
        return {'entries':entries, 'balances':balances}

    @atomic
    def supplier_pay(self, uid, supplier, amount, note='', date=None, currency='USD', manager=None, method=''):
        from core import now, money
        self.user(uid)
        self.supplier_row(supplier)
        if manager is None:
            self.director(uid)
        else:
            self._manager_access(uid, manager)
        amount = money(amount, True)
        currency, stamp, note = valid_currency(currency), accounting_date(date), clean_note(note)
        if method and method not in ('cash','transfer','card'):raise ValueError('payment')
        manager_entry = None
        if manager is not None:
            # One payment reduces both supplier debt and the manager's cash once.
            from core import fmt
            manager_entry = self.manager_record(uid, manager, 'expense', fmt(amount).replace(' ', ''), note, stamp, currency)
        ref = self.add('supplier_entries', supplier=supplier, kind='payment', amount=amount, currency=currency, method=method, manager_entry=manager_entry, actor=uid, note=note, date=stamp, created=now())
        self.log(uid, 'supplier_payment', ref)
        return ref

    @atomic
    def supplier_return(self, uid, lot, qty, note='', date=None):
        from core import now
        self.director(uid)
        qty = quantity(qty)
        rows = self.rows('SELECT l.*,r.supplier,r.cost,r.currency FROM inventory_lots l JOIN receipts r ON r.id=l.receipt WHERE l.id=?', (quantity(lot),))
        if not rows:
            raise ValueError('supplier_lot')
        row = rows[0]
        note, stamp = clean_note(note), accounting_date(date)
        if not self.db.execute('UPDATE inventory_lots SET qty=qty-? WHERE id=? AND qty>=?', (qty, lot, qty)).rowcount:
            raise ValueError('stock')
        if not self.db.execute('UPDATE stock SET qty=qty-? WHERE product=? AND point=? AND qty>=?', (qty, row['product'], row['point'], qty)).rowcount:
            raise ValueError('stock')
        ref = self.add('supplier_entries', supplier=row['supplier'], kind='return', amount=qty*row['cost'], currency=row['currency'], receipt=row['receipt'], lot=lot, qty=qty, actor=uid, note=note, date=stamp, created=now())
        self.add('movements', product=row['product'], point=row['point'], qty=-qty, kind='supplier_return', actor=uid, note=f'#{ref}: {note}', created=now())
        self.log(uid, 'supplier_return', ref)
        return ref

    def supplier_report(self, uid, start, end, supplier=None):
        self.director(uid)
        start, end = accounting_date(start), accounting_date(end)
        if start > end:
            raise ValueError('date')
        if supplier is not None:
            self.supplier_row(supplier)
        # NULL remains a distinct, visible supplier bucket for legacy stock/sales.
        where = '' if supplier is None else ' AND r.supplier=?'
        params = () if supplier is None else (supplier,)
        stock = self.rows("SELECT r.supplier,COALESCE(v.name,'Yetkazib beruvchi belgilanmagan') supplier_name,p.id product,p.name,t.id point,t.name point_name,SUM(l.qty) qty FROM inventory_lots l LEFT JOIN receipts r ON r.id=l.receipt LEFT JOIN suppliers v ON v.id=r.supplier JOIN products p ON p.id=l.product JOIN points t ON t.id=l.point WHERE t.kind='vitrina' AND l.qty>0"+where+' GROUP BY r.supplier,l.product,l.point ORDER BY p.id,t.id,r.supplier', params)
        sold = self.rows("SELECT r.supplier,COALESCE(v.name,'Yetkazib beruvchi belgilanmagan') supplier_name,i.product,i.name,t.id point,t.name point_name,s.currency,SUM(a.qty) qty FROM sale_allocations a JOIN inventory_lots l ON l.id=a.lot LEFT JOIN receipts r ON r.id=l.receipt LEFT JOIN suppliers v ON v.id=r.supplier JOIN sale_items i ON i.id=a.item JOIN sales s ON s.id=i.sale JOIN points t ON t.id=COALESCE(i.point,s.point) WHERE COALESCE(i.location_kind,t.kind)='vitrina' AND s.status='active' AND substr(s.created,1,10) BETWEEN ? AND ?"+where+' GROUP BY r.supplier,i.product,t.id,s.currency ORDER BY i.product,t.id,r.supplier', (start, end, *params))
        # Historical sales have no allocation rows; report them without attribution.
        if supplier is None:
            sold += self.rows("SELECT NULL supplier,'Yetkazib beruvchi belgilanmagan' supplier_name,i.product,i.name,t.id point,t.name point_name,s.currency,SUM(i.qty) qty FROM sale_items i JOIN sales s ON s.id=i.sale JOIN points t ON t.id=COALESCE(i.point,s.point) WHERE COALESCE(i.location_kind,t.kind)='vitrina' AND s.status='active' AND substr(s.created,1,10) BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM sale_allocations a WHERE a.item=i.id) GROUP BY i.product,t.id,s.currency", (start, end))
        scope = '' if supplier is None else ' AND e.supplier=?'
        entries = self.rows('SELECT e.*,v.name supplier_name,u.name actor_name FROM supplier_entries e JOIN suppliers v ON v.id=e.supplier JOIN users u ON u.id=e.actor WHERE e.date BETWEEN ? AND ?'+scope+' ORDER BY e.id', (start, end, *params))
        lots = self.rows('SELECT l.*,r.supplier,r.cost,r.currency,p.name product_name,t.name point_name FROM inventory_lots l JOIN receipts r ON r.id=l.receipt JOIN products p ON p.id=l.product JOIN points t ON t.id=l.point WHERE l.qty>0'+where+' ORDER BY l.id', params)
        return {'stock':stock, 'sold':sold, 'entries':entries, 'lots':lots, 'balances':[r for r in self.suppliers(uid)['balances'] if supplier is None or r['supplier']==supplier], 'start':start, 'end':end}

    def supplier_ledger(self, uid, supplier):
        """Return a supplier's itemized ledger with actor, timestamp, and running balance."""
        self.director(uid)
        supplier = quantity(supplier)
        row = self.supplier_row(supplier)
        totals = self.rows(
            "SELECT currency,"
            "SUM(CASE WHEN kind='receipt' THEN amount ELSE 0 END) received,"
            "SUM(CASE WHEN kind='payment' THEN amount ELSE 0 END) paid,"
            "SUM(CASE WHEN kind='return' THEN amount ELSE 0 END) returned,"
            "SUM(CASE WHEN kind='receipt' THEN amount ELSE -amount END) balance "
            "FROM supplier_entries WHERE supplier=? GROUP BY currency ORDER BY currency",
            (supplier,),
        )
        entries = self.rows(
            """SELECT e.*,u.name actor_name,r.id receipt_id,r.product product,
                      p.name product_name,r.qty receipt_qty,r.cost unit_cost,
                      (SELECT GROUP_CONCAT(t.name || ' × ' || (
                           l.qty
                           + COALESCE((SELECT SUM(a.qty) FROM sale_allocations a WHERE a.lot=l.id),0)
                           + COALESCE((SELECT SUM(x.qty) FROM supplier_entries x WHERE x.kind='return' AND x.lot=l.id),0)
                       ), ', ')
                       FROM inventory_lots l JOIN points t ON t.id=l.point
                       WHERE l.receipt=r.id) locations
               FROM supplier_entries e
               JOIN users u ON u.id=e.actor
               LEFT JOIN receipts r ON r.id=e.receipt
               LEFT JOIN products p ON p.id=COALESCE(r.product,(SELECT product FROM inventory_lots WHERE id=e.lot))
               WHERE e.supplier=?
               ORDER BY e.created,e.id""",
            (supplier,),
        )
        running = {}
        for entry in entries:
            currency = entry['currency']
            change = entry['amount'] if entry['kind'] == 'receipt' else -entry['amount']
            running[currency] = running.get(currency, 0) + change
            entry['balance_after'] = running[currency]
        return {'supplier':row, 'totals':totals, 'entries':entries}
