"""Director-only named filters, client editing and chronological debt projections."""
import hashlib
import json
import re
from accounting import atomic,quantity,clean_note
from core import normalize_contact_phone
from manager_money import read_snapshot


def revision(row):
    return hashlib.sha256(json.dumps({k:row[k] for k in ('name','phone','address','note','owner')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@atomic
def save_client(s,uid,d):
    s.director(uid)
    old=s.one('clients',quantity(d['client'])) if d.get('client') else None
    if old and d.get('revision')!=revision(old):raise ValueError('client_changed')
    fields=dict(name=clean_note(d.get('name',''),True,150),phone=normalize_contact_phone(d['phone']) if str(d.get('phone','')).strip() else '',address=clean_note(d.get('address',''),False,1000),note=clean_note(d.get('note',''),False,1500))
    owner=d.get('owner',old['owner'] if old else uid)
    if isinstance(owner,bool) or not str(owner).isdigit() or not 0<int(owner)<=2**53:raise ValueError('staff_target')
    owner=int(owner);s.one('users',owner)
    if not old or owner!=old['owner']:s.user(owner)
    if old:
        s.db.execute('UPDATE clients SET name=?,phone=?,address=?,note=?,owner=? WHERE id=?',(*fields.values(),owner,old['id']))
        ref=old['id'];s.log(uid,'client_edit:'+json.dumps({'before':{k:old[k] for k in fields},'after':fields,'owner_before':old['owner'],'owner_after':owner},ensure_ascii=False),ref)
    else:
        ref=s.client(uid,**fields);s.db.execute('UPDATE clients SET owner=? WHERE id=?',(owner,ref))
    return ref


def filtered(rows,q,kind=''):
    result=[]
    for row in rows:
        keep=True
        for key,columns in {'currency':['currency'],'manager':['manager','actor','owner'],'owner':['owner'],'client':['client'],'supplier':['supplier'],'point':['point_id','point'],'role':['role'],'kind':['kind'],'status':['status'],'receipt_status':['receipt_status'],'sync_status':['sync_status'],'brand':['brand'],'method':['method']}.items():
            value=q.get(key)
            if not value:continue
            column=next((c for c in columns if c in row),None)
            if column is not None:
                actual=str(row[column]).casefold();expected=str(value).casefold()
                if key=='method':
                    aliases={'naqd':'cash','karta':'card','perechisleniya':'transfer'};actual=aliases.get(actual,actual);expected=aliases.get(expected,expected)
                if actual!=expected:keep=False;break
        if q.get('size') and re.sub(r'\s','',q['size']).casefold() not in re.sub(r'\s','',str(row.get('size',''))).casefold():keep=False
        state=q.get('stock_status')
        if state:
            qty=row.get('qty')
            if state=='unknown' and qty is not None or state=='known' and qty is None or state=='available' and (qty is None or qty<=0) or state=='empty' and qty!=0:keep=False
        if q.get('active') in ('0','1') and 'active' in row and bool(row['active'])!=(q['active']=='1'):keep=False
        if keep:result.append(row)
    return result


def client_list(s,uid,q):
    from core import now
    s.director(uid)
    debts=s.debts(uid);grouped={}
    for r in debts:
        g=grouped.setdefault(r['client'],[]);g.append(r)
    rows=s.rows('SELECT c.*,u.name owner_name FROM clients c JOIN users u ON u.id=c.owner ORDER BY c.id DESC')
    for r in rows:
        selected=[d for d in grouped.get(r['id'],[]) if not q.get('currency') or d['currency']==q['currency']]
        r['debt_currencies']=sorted({d['currency'] for d in selected});r['has_debt']=bool(selected);r['overdue']=any(d['debt_due'] and d['debt_due']<now()[:10] for d in selected);r['revision']=revision(r)
    state=q.get('debt_status')
    if state=='debt':rows=[r for r in rows if r['has_debt']]
    if state=='clear':rows=[r for r in rows if not r['has_debt']]
    if state=='overdue':rows=[r for r in rows if r['overdue']]
    return filtered(rows,q,'clients')


def rollforward(events,start,end):
    running={};opening={};visible=[]
    for r in sorted(events,key=lambda x:(x['date'],x.get('created',''),x.get('priority',0),x.get('source_id',0))):
        c=r['currency'];running[c]=running.get(c,0)+r['change']
        if r['date']<start:opening[c]=running[c]
        elif r['date']<=end:visible.append({**r,'balance_after':running[c]})
    currencies=sorted({r['currency'] for r in events})
    closing={c:opening.get(c,0) for c in currencies}
    for r in visible:closing[r['currency']]=r['balance_after']
    return {'entries':visible,'opening':[dict(currency=c,balance=opening.get(c,0)) for c in currencies],'period_closing':[dict(currency=c,balance=closing[c]) for c in currencies]}


def client_card(s,uid,ref,start,end):
    s.director(uid)
    with read_snapshot(s):
        result=s.client_card(uid,ref);client=result['client'][0];client['revision']=revision(client);client['owner_name']=s.one('users',client['owner'])['name']
        payments=s.rows('SELECT p.*,u.name actor_name FROM payments p JOIN sales s ON s.id=p.sale JOIN users u ON u.id=p.actor WHERE s.client=? ORDER BY p.id',(ref,));result['payments']=payments
        result['debts']=[r for r in s.debts(uid) if r['client']==ref]
        events=[];review=[]
        descriptions={r['id']:', '.join(i['name']+' × '+str(i['qty']) for i in s.rows('SELECT name,qty FROM sale_items WHERE sale=?',(r['id'],))) for r in result['sales']}
        for row in result['sales']:
            events.append(dict(source='sale',source_id=row['id'],sale=row['id'],date=row['created'][:10],created=row['created'],kind='sale_debt',amount=row['total'],change=row['total'],currency=row['currency'],actor_name=s.one('users',row['actor'])['name'],priority=0,note=''))
            actual=sum(p['amount'] for p in payments if p['sale']==row['id'] and p['currency']==row['currency'])
            if actual!=row['paid']:review.append(row['id'])
            if row['status']=='cancelled':
                stamp=row['cancelled_at'] or row['created'];events.append(dict(source='cancellation',source_id=row['id'],sale=row['id'],date=stamp[:10],created=stamp,kind='sale_cancelled',amount=row['total'],change=-row['total'],currency=row['currency'],actor_name=s.one('users',row['cancelled_by'])['name'] if row['cancelled_by'] else '',priority=3,note=row['cancel_reason']))
        for p in payments:events.append(dict(source='payment',source_id=p['id'],sale=p['sale'],date=p['created'][:10],created=p['created'],kind='client_payment',method=p['method'],amount=p['amount'],change=-p['amount'],currency=p['currency'],actor_name=p['actor_name'],priority=1,note=''))
        for r in result['refunds']:events.append(dict(source='refund',source_id=r['id'],sale=r['sale'],date=r['created'][:10],created=r['created'],kind='client_refund',amount=r['amount'],change=r['amount'],currency=r['currency'],actor_name=s.one('users',r['actor'])['name'],priority=2,note=r['reason']))
        for event in events:event['product_name']=descriptions.get(event['sale'],'')
        result['ledger']=rollforward(events,start,end);result['history_review_count']=len(review);result['start']=start;result['end']=end
        return result


def supplier_card(s,uid,ref,start,end):
    with read_snapshot(s):
        result=s.supplier_ledger(uid,ref);events=[]
        for r in result['entries']:
            change=r['amount'] if r['kind']=='receipt' else -r['amount']
            events.append({**r,'date':r['date'],'source_id':r['id'],'change':change,'priority':0})
        result['ledger']=rollforward(events,start,end);result['start']=start;result['end']=end
        return result
