"""Read-only employee sale history. Scope is authenticated actor, never client owner."""
from accounting import accounting_date,quantity
from core import now
from manager_money import read_snapshot


def history(s,uid,q,employee=None):
    viewer=s.user(uid)
    target=employee if employee is not None else (None if viewer['role']=='director' else uid)
    if target is not None:
        target=quantity(target);s.one('users',target)
        if target!=uid:s.director(uid)
    start=accounting_date(q.get('start') or '1900-01-01');end=accounting_date(q.get('end') or now()[:10])
    if start>end:raise ValueError('date')
    clauses=[];params=[]
    if target is not None:clauses.append('s.actor=?');params.append(target)
    scoped=' AND '.join(clauses) or '1=1';scoped_params=list(params)
    clauses+=['substr(s.created,1,10) BETWEEN ? AND ?'];params += [start,end]
    if q.get('sale'):
        ref=quantity(q['sale'])
        if not s.db.execute('SELECT 1 FROM sales s WHERE s.id=? AND '+scoped,(ref,*scoped_params)).fetchone():raise PermissionError()
        clauses.append('s.id=?');params.append(ref)
    for key in ('client','currency','status'):
        if q.get(key):
            if key=='client':value=quantity(q[key])
            elif key=='currency' and q[key] not in ('USD','UZS'):raise ValueError('currency')
            elif key=='status' and q[key] not in ('active','cancelled'):raise ValueError('status')
            else:value=q[key]
            clauses.append('s.'+key+'=?');params.append(value)
    if q.get('payment_status'):
        if q['payment_status'] not in ('paid','debt'):raise ValueError('status')
        clauses.append("s.status='active' AND s.total"+('>s.paid' if q['payment_status']=='debt' else '=s.paid'))
    if q.get('q','').strip():
        search='%'+q['q'].strip()[:200].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        clauses.append("(c.name LIKE ? ESCAPE '\\' OR c.phone LIKE ? ESCAPE '\\' OR EXISTS(SELECT 1 FROM sale_items i WHERE i.sale=s.id AND i.name LIKE ? ESCAPE '\\'))");params += [search]*3
    where=' AND '.join(clauses);join=' FROM sales s JOIN clients c ON c.id=s.client WHERE '+where
    page=max(0,min(100000,int(q.get('page',0))));size=20
    with read_snapshot(s):
        rows=s.rows("SELECT s.id,s.client,c.name client_name,s.created,s.total,s.paid,CASE WHEN s.status='active' THEN s.total-s.paid ELSE 0 END debt,s.currency,s.status,s.debt_due,s.cancelled_at,s.cancel_reason"+join+' ORDER BY s.created DESC,s.id DESC LIMIT ? OFFSET ?',(*params,size,page*size))
        for row in rows:
            row['items']=s.rows('SELECT i.name,i.qty,i.price,i.discount,t.name point_name FROM sale_items i JOIN points t ON t.id=COALESCE(i.point,?) WHERE i.sale=?',(s.one('sales',row['id'])['point'],row['id']))
            row['payments']=s.rows('SELECT amount,method,currency,created FROM payments WHERE sale=? ORDER BY created,id',(row['id'],))
            row['payment_history_complete']=sum(p['amount'] for p in row['payments'] if p['currency']==row['currency'])==row['paid']
            row['refunds']=s.rows('SELECT amount,currency,created,reason FROM refunds WHERE sale=? ORDER BY id',(row['id'],))
            for item in row['items']:item['currency']=row['currency']
        total=s.db.execute('SELECT COUNT(*)'+join,params).fetchone()[0]
        sums="COUNT(CASE WHEN s.status='active' THEN 1 END) sales_count,SUM(CASE WHEN s.status='active' THEN s.total ELSE 0 END) sales_total,SUM(CASE WHEN s.status='active' THEN s.paid ELSE 0 END) paid_to_date,SUM(CASE WHEN s.status='active' THEN s.total-s.paid ELSE 0 END) debt_to_date,COUNT(CASE WHEN s.status='cancelled' THEN 1 END) cancelled_count"
        totals=s.rows('SELECT s.currency,'+sums+join+' GROUP BY s.currency',params)
        days=s.rows('SELECT substr(s.created,1,10) date,s.currency,'+sums+join+' GROUP BY substr(s.created,1,10),s.currency ORDER BY date DESC,s.currency',params)
        clients=s.rows('SELECT DISTINCT c.id,c.name FROM clients c JOIN sales s ON s.client=c.id WHERE '+scoped+' ORDER BY c.name,c.id',scoped_params)
    return dict(items=rows,total=total,page=page,page_size=size,start=start,end=end,summary=totals,days=days,clients=clients,employee_name=s.one('users',target)['name'] if target else '',as_of=now())


def bot_sale_text(s,uid,row,lang):
    from core import fmt
    from reports import localized
    sale=s.one('sales',row['id']);s.user(uid);s.own(uid,sale)
    t=lambda uz,ru:ru if lang=='ru' else uz
    currency=sale['currency'];debt=sale['total']-sale['paid'] if sale['status']=='active' else 0
    lines=[row['client_name'],sale['created'],t('Savdo summasi','Сумма продажи')+': '+fmt(sale['total'])+' '+currency,t('To‘langan','Оплачено')+': '+fmt(sale['paid'])+' '+currency,t('Qolgan qarz','Остаток долга')+': '+fmt(debt)+' '+currency,t('Holat','Статус')+': '+localized('status',sale['status'],lang)]
    if sale['debt_due']:lines.append(t('To‘lov muddati','Срок оплаты')+': '+sale['debt_due'])
    for item in s.rows('SELECT name,qty,price FROM sale_items WHERE sale=? ORDER BY id',(sale['id'],)):lines.append(item['name']+' × '+str(item['qty'])+' · '+fmt(item['price'])+' '+currency)
    return '\n'.join(lines)
