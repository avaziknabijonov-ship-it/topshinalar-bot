"""Manager custody: actual payments, accepted handovers and independent day closing.
No cash/bank general ledger and no sales-total based manager debt.
"""
import hashlib
import json
from contextlib import contextmanager
from functools import wraps
from accounting import transaction,atomic,quantity,accounting_date,clean_note,valid_currency


def migrate(s):
    from core import now
    with s.db,transaction(s):
        for sql in (
            '''CREATE TABLE IF NOT EXISTS manager_return_receipts(entry INTEGER PRIMARY KEY REFERENCES manager_entries(id),accepted_by INTEGER REFERENCES users(id),accepted_at TEXT)''',
            '''CREATE TABLE IF NOT EXISTS manager_received(id INTEGER PRIMARY KEY,manager INTEGER NOT NULL REFERENCES users(id),amount INTEGER NOT NULL CHECK(amount>0),currency TEXT NOT NULL CHECK(currency IN ('USD','UZS')),date TEXT NOT NULL,note TEXT NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),created TEXT NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS manager_refund_payers(refund INTEGER PRIMARY KEY REFERENCES refunds(id),manager INTEGER REFERENCES users(id),actor INTEGER NOT NULL REFERENCES users(id),note TEXT NOT NULL,created TEXT NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS manager_day_closings(id INTEGER PRIMARY KEY,manager INTEGER NOT NULL REFERENCES users(id),date TEXT NOT NULL,fingerprint TEXT NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),note TEXT NOT NULL,created TEXT NOT NULL)''',
            'CREATE INDEX IF NOT EXISTS manager_closing_date ON manager_day_closings(manager,date,id)',
        ):s.db.execute(sql)
        columns={r[1] for r in s.db.execute('PRAGMA table_info(manager_return_receipts)')}
        for column,definition in [('rejected_by','INTEGER REFERENCES users(id)'),('rejected_at','TEXT'),('reject_reason',"TEXT NOT NULL DEFAULT ''")]:
            if column not in columns:s.db.execute(f'ALTER TABLE manager_return_receipts ADD COLUMN {column} {definition}')
        s.db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('manager_money_since',?)",(now(),))


@contextmanager
def read_snapshot(s):
    owner=not s.db.in_transaction
    if owner:s.db.execute('BEGIN')
    try:
        yield
        if owner:s.db.commit()
    except Exception:
        if owner:s.db.rollback()
        raise


def consistent(fn):
    @wraps(fn)
    def wrapped(s,*args,**kwargs):
        with read_snapshot(s):return fn(s,*args,**kwargs)
    return wrapped


def cash_date(value=None):
    from core import now
    date=accounting_date(value)
    if date>now()[:10]:raise ValueError('date')
    return date


def access(s,uid,manager=None):
    user=s.user(uid)
    if manager is None:return None if user['role']=='director' else uid
    if isinstance(manager,bool) or not str(manager).isdigit() or not 0<int(manager)<=2**53:raise ValueError('manager')
    manager=int(manager)
    if manager!=uid:s.director(uid)
    s.one('users',manager)
    return manager


@consistent
def account(s,uid,manager=None,through=None):
    from payments import normalize_payment
    manager=access(s,uid,manager)
    if through is not None:through=accounting_date(through)
    scope='' if manager is None else ' WHERE e.manager=?';params=() if manager is None else (manager,)
    entries=s.rows('''SELECT e.*,u.name manager_name,a.name actor_name,h.accepted_by,h.accepted_at,receiver.name accepted_by_name,h.rejected_by,h.rejected_at,h.reject_reason,
        CASE WHEN e.kind<>'return' THEN '' WHEN h.entry IS NULL THEN 'legacy' WHEN h.rejected_by IS NOT NULL THEN 'rejected' WHEN h.accepted_by IS NULL THEN 'pending' ELSE 'accepted' END receipt_status
        FROM manager_entries e JOIN users u ON u.id=e.manager JOIN users a ON a.id=e.actor LEFT JOIN manager_return_receipts h ON h.entry=e.id LEFT JOIN users receiver ON receiver.id=h.accepted_by'''+scope,params)
    for r in entries:r['source']='manager_entry';r['source_id']=r['id'];r['method']=''
    scope='' if manager is None else ' WHERE p.actor=?'
    payments=s.rows('SELECT p.*,u.name actor_name FROM payments p JOIN users u ON u.id=p.actor'+scope,params)
    for p in payments:
        entries.append(dict(id=p['id'],source='payment',source_id=p['id'],kind='sale_receipt',manager=p['actor'],manager_name=p['actor_name'],actor=p['actor'],actor_name=p['actor_name'],amount=p['amount'],currency=p['currency'],method=p['method'],sale=p['sale'],date=p['created'][:10],created=p['created'],note='',receipt_status=''))
    scope='' if manager is None else ' WHERE e.manager=?'
    for r in s.rows('SELECT e.*,u.name manager_name,a.name actor_name FROM manager_received e JOIN users u ON u.id=e.manager JOIN users a ON a.id=e.actor'+scope,params):
        entries.append({**r,'source':'received','source_id':r['id'],'kind':'received','method':'','receipt_status':''})
    scope='' if manager is None else ' AND p.manager=?'
    for r in s.rows('SELECT f.*,p.manager,p.actor approved_by,p.created approved_at,p.note approval_note,u.name manager_name,a.name actor_name FROM refunds f JOIN manager_refund_payers p ON p.refund=f.id JOIN users u ON u.id=p.manager JOIN users a ON a.id=f.actor WHERE p.manager IS NOT NULL'+scope,params):
        entries.append(dict(id=r['id'],source='refund',source_id=r['id'],kind='customer_refund',manager=r['manager'],manager_name=r['manager_name'],actor=r['actor'],actor_name=r['actor_name'],approved_by=r['approved_by'],approved_at=r['approved_at'],amount=r['amount'],currency=r['currency'],method=r['method'],sale=r['sale'],date=r['created'][:10],created=r['created'],note=r['approval_note'],receipt_status=''))
    if through:entries=[r for r in entries if r['date']<=through]
    balances={};since=s.db.execute("SELECT value FROM meta WHERE key='manager_money_since'").fetchone()[0]
    for r in entries:
        key=(r['manager'],r['currency'])
        b=balances.setdefault(key,dict(manager=r['manager'],manager_name=r['manager_name'],currency=r['currency'],given=0,received=0,received_cash=0,received_card=0,received_transfer=0,received_other=0,historical_received=0,expenses=0,returned=0,legacy_returned=0,pending_return=0,refunds=0,balance=0))
        if r['kind']=='fund':b['given']+=r['amount'];b['balance']+=r['amount']
        elif r['kind'] in ('sale_receipt','received'):
            b['received']+=r['amount'];b['balance']+=r['amount']
            method='other'
            if r['kind']=='sale_receipt':
                try:method={'naqd':'cash','karta':'card','perechisleniya':'transfer'}[normalize_payment(r['method'])]
                except (ValueError,KeyError):pass
                if r['created']<since:b['historical_received']+=r['amount']
            b['received_'+method]+=r['amount']
        elif r['kind']=='expense':b['expenses']+=r['amount'];b['balance']-=r['amount']
        elif r['kind']=='customer_refund':b['refunds']+=r['amount'];b['balance']-=r['amount']
        elif r['kind']=='return':
            if r['receipt_status']=='pending':b['pending_return']+=r['amount']
            elif r['receipt_status'] in ('accepted','legacy'):
                b['returned']+=r['amount'];b['balance']-=r['amount']
                if r['receipt_status']=='legacy':b['legacy_returned']+=r['amount']
    review=s.rows('''SELECT DISTINCT f.*,p.actor manager,u.name manager_name FROM refunds f JOIN payments p ON p.sale=f.sale JOIN users u ON u.id=p.actor WHERE f.amount>0 AND NOT EXISTS(SELECT 1 FROM manager_refund_payers x WHERE x.refund=f.id)'''+('' if manager is None else ' AND p.actor=?'),params)
    if through:review=[r for r in review if r['created'][:10]<=through]
    for b in balances.values():b['refund_review_count']=sum(r['manager']==b['manager'] and r['currency']==b['currency'] for r in review)
    return dict(entries=sorted(entries,key=lambda r:(r['date'],r['created'],r['source'],r['source_id']),reverse=True),balances=sorted(balances.values(),key=lambda b:(b['manager'],b['currency'])),refund_review=review)


def balance(s,uid,manager,currency):
    return next((r for r in account(s,uid,manager)['balances'] if r['currency']==currency),dict(balance=0,pending_return=0))


@atomic
def receive(s,uid,d):
    from core import money,now
    s.director(uid);manager=access(s,uid,d['manager'])
    ref=s.add('manager_received',manager=manager,amount=money(d['amount'],True),currency=valid_currency(d.get('currency','USD')),date=cash_date(d.get('date')),note=clean_note(d.get('note',''),True),actor=uid,created=now())
    s.log(uid,'manager_received',ref);return ref


@atomic
def request_return(s,uid,d):
    from core import money,now
    manager=access(s,uid,d.get('manager',uid))
    amount=money(d['amount'],True);currency=valid_currency(d.get('currency','USD'))
    b=balance(s,uid,manager,currency)
    if amount>b['balance']-b['pending_return']:raise ValueError('manager_cash_available')
    ref=s.add('manager_entries',manager=manager,kind='return',amount=amount,currency=currency,date=cash_date(d.get('date')),note=clean_note(d.get('note',''),True),actor=uid,created=now())
    s.db.execute('INSERT INTO manager_return_receipts(entry) VALUES(?)',(ref,));s.log(uid,'manager_handover_requested',ref)
    return ref


@atomic
def accept_return(s,uid,d):
    from core import now
    s.director(uid);ref=quantity(d['entry'])
    row=s.db.execute("SELECT e.* FROM manager_entries e JOIN manager_return_receipts h ON h.entry=e.id WHERE e.id=? AND h.accepted_by IS NULL AND h.rejected_by IS NULL AND e.kind='return'",(ref,)).fetchone()
    if not row:raise ValueError('manager_handover_changed')
    if row['amount']>balance(s,uid,row['manager'],row['currency'])['balance']:raise ValueError('manager_cash_available')
    if not s.db.execute('UPDATE manager_return_receipts SET accepted_by=?,accepted_at=? WHERE entry=? AND accepted_by IS NULL AND rejected_by IS NULL',(uid,now(),ref)).rowcount:raise ValueError('manager_handover_changed')
    s.log(uid,'manager_handover_accepted',ref);return ref


@atomic
def reject_return(s,uid,d):
    from core import now
    s.director(uid);ref=quantity(d['entry']);note=clean_note(d.get('note',''),True)
    if not s.db.execute('UPDATE manager_return_receipts SET rejected_by=?,rejected_at=?,reject_reason=? WHERE entry=? AND accepted_by IS NULL AND rejected_by IS NULL',(uid,now(),note,ref)).rowcount:raise ValueError('manager_handover_changed')
    s.log(uid,'manager_handover_rejected',ref);return ref


@atomic
def accept_cash(s,uid,d):
    s.director(uid)
    ref=request_return(s,uid,d);accept_return(s,uid,dict(entry=ref));return ref


@atomic
def assign_refund(s,uid,d):
    from core import now
    s.director(uid);ref=quantity(d['refund'])
    if not s.db.execute('SELECT 1 FROM refunds WHERE id=? AND amount>0',(ref,)).fetchone():raise ValueError('missing')
    manager=None if d.get('manager') in (None,'',0) else access(s,uid,d['manager'])
    s.db.execute('INSERT INTO manager_refund_payers VALUES(?,?,?,?,?)',(ref,manager,uid,clean_note(d.get('note',''),True),now()))
    s.log(uid,'manager_refund_payer',ref);return ref


def fingerprint(data):
    # Include accepted receipts and unresolved refunds: backdated changes reopen a day.
    payload={'entries':[{k:v for k,v in r.items() if k not in ('manager_name','actor_name','accepted_by_name')} for r in data['entries']],'refunds':[{k:v for k,v in r.items() if k!='manager_name'} for r in data['refund_review']]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


@atomic
def close_day(s,uid,d):
    from core import now
    s.director(uid);manager=access(s,uid,d['manager']);date=accounting_date(d['date'])
    if date>now()[:10]:raise ValueError('date')
    data=account(s,uid,manager,date);stamp=fingerprint(data)
    if any(r['balance'] or r['pending_return'] for r in data['balances']) or data['refund_review']:raise ValueError('manager_day_unsettled')
    old=s.db.execute('SELECT fingerprint FROM manager_day_closings WHERE manager=? AND date=? ORDER BY id DESC LIMIT 1',(manager,date)).fetchone()
    if old and old['fingerprint']==stamp:raise ValueError('manager_day_closed')
    ref=s.add('manager_day_closings',manager=manager,date=date,fingerprint=stamp,actor=uid,note=clean_note(d.get('note',''),True),created=now())
    s.log(uid,'manager_day_closed',ref);return ref


@consistent
def days(s,uid,start,end):
    s.director(uid)
    data=account(s,uid);keys={(r['manager'],r['date']) for r in data['entries'] if start<=r['date']<=end}
    currencies={}
    for r in s.rows('SELECT actor,currency,substr(created,1,10) date FROM sales WHERE substr(created,1,10) BETWEEN ? AND ?',(start,end)):
        keys.add((r['actor'],r['date']));currencies.setdefault((r['actor'],r['date']),set()).add(r['currency'])
    closings=s.rows('SELECT c.*,u.name actor_name FROM manager_day_closings c JOIN users u ON u.id=c.actor WHERE c.date BETWEEN ? AND ? ORDER BY c.id',(start,end));latest={(r['manager'],r['date']):r for r in closings};keys.update(latest)
    result=[]
    for manager,date in sorted(keys,reverse=True):
        snapshot=account(s,uid,manager,date);closing=latest.get((manager,date));state='open'
        if closing:state='closed' if closing['fingerprint']==fingerprint(snapshot) else 'reopened'
        day_balances=list(snapshot['balances'])
        for currency in currencies.get((manager,date),set())-{r['currency'] for r in day_balances}:day_balances.append(dict(currency=currency,balance=0,pending_return=0))
        for b in day_balances or [dict(currency='',balance=0,pending_return=0)]:
            result.append(dict(manager=manager,manager_name=s.one('users',manager)['name'],date=date,currency=b['currency'],balance=b['balance'],pending_return=b['pending_return'],day_status=state,closed_by=closing['actor_name'] if closing else '',closed_at=closing['created'] if closing else '',refund_review=len(snapshot['refund_review'])))
    return result
