"""Read-only dashboard projections over the existing accounting and import models."""
from datetime import date,timedelta
from core import now
from manager_money import read_snapshot,days


def totals(rows,field):
    grouped={}
    for row in rows:
        currency=row['currency'];value=row[field]
        r=grouped.setdefault(currency,dict(currency=currency,debt=0,credit=0))
        if value>0:r['debt']+=value
        elif value<0:r['credit']-=value
    return sorted(grouped.values(),key=lambda x:x['currency'])


def overview(service,uid,start,end):
    s=service.s;s.director(uid)
    with read_snapshot(s):
        result=service.dashboard(uid,start,end)
        result['as_of']=now()
        result['lowstock']=[r for r in result['lowstock'] if s.db.execute('SELECT 1 FROM stock WHERE product=? AND point=?',(r['product'],r['point'])).fetchone()]
        suppliers=s.suppliers(uid);names={r['id']:r['name'] for r in suppliers['suppliers']}
        result['supplier_balances']=[{**r,'supplier_name':names.get(r['supplier'],'')} for r in suppliers['balances']]
        result['supplier_totals']=totals(result['supplier_balances'],'balance')
        money=s.manager_account(uid);result['manager_totals']=totals(money['balances'],'balance')
        result['manager_review_count']=len(money['refund_review'])
        result['pending_handovers']=sum(r['kind']=='return' and r['receipt_status']=='pending' for r in money['entries'])
        day_rows=days(s,uid,start,end)
        result['open_money_days']=len({(r['manager'],r['date']) for r in day_rows if r['day_status']!='closed'})
        result['open_shifts']=s.db.execute('SELECT COUNT(*) FROM shifts WHERE ended IS NULL').fetchone()[0]
        result['recent']=s.rows('SELECT a.id,a.created,a.action,a.ref,u.name actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 7')
        report=s.report(uid,start,end)
        # Money remains integer cents. Only chart geometry uses fractional numbers.
        begin=date.fromisoformat(start);finish=date.fromisoformat(end);span=(finish-begin).days+1;width=max(1,(span+44)//45)
        bins=[dict(date=(begin+timedelta(days=i)).isoformat(),sales=0,received=0) for i in range(0,span,width)]
        for kind,field in [('sales','total'),('payments','amount')]:
            for row in report[kind]:
                if row['currency']!='USD' or kind=='sales' and row['status']!='active':continue
                index=(date.fromisoformat(row['created'][:10])-begin).days//width
                bins[index]['sales' if kind=='sales' else 'received']+=row[field]
        result['trend']=bins;result['trend_bucket_days']=width
        result['recent_sales']=s.rows('SELECT s.id,s.created,s.total,s.currency,s.status,c.name client_name,u.name manager_name FROM sales s JOIN clients c ON c.id=s.client JOIN users u ON u.id=s.actor WHERE substr(s.created,1,10) BETWEEN ? AND ? ORDER BY s.id DESC LIMIT 6',(start,end))
        result['overdue_tasks']=sum(r['due'][:10]<=now()[:10] for r in report['tasks'])
        result['products_active']=s.db.execute('SELECT COUNT(*) FROM products WHERE active=1').fetchone()[0]
        result['net_received']=result['received']-result['refunds']
        result['profit']=None;result['cash_balance']=None
        result['financial_note']='Hisoblash uchun ma’lumot yetarli emas / Недостаточно данных для расчёта'
        return result
