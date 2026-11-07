"""Selectable director exports. Transactions use the period; balances are current."""
from accounting import accounting_date
from core import now
from manager_money import read_snapshot,days
from director_business import client_list,client_card,supplier_card,filtered
from bot import Bot
import json
from types import SimpleNamespace

GROUPS={
 'product_analytics':(('Tovarlar tahlili','Аналитика товаров'),('product_analytics','analytics_review')),
 'employee_analytics':(('Xodimlar tahlili','Аналитика сотрудников'),('employee_analytics',)),
 'products':(('Mahsulotlar · joriy','Товары · сейчас'),('products',)),
 'expenses':(('Menejer xarajatlari','Расходы менеджеров'),('expenses',)),
 'customer_returns':(('Mijozdan qaytarishlar','Возвраты клиентов'),('customer_returns',)),
 'supplier_returns':(('Ta’minotchiga qaytarishlar','Возвраты поставщикам'),('supplier_returns',)),
 'sales':(('Savdolar','Продажи'),('sales','sale_items')),
 'payments':(('Tushum va pul qaytarish','Поступления и возвраты'),('payments','refunds')),
 'debts':(('Mijozlar qarzi · joriy','Долги клиентов · сейчас'),('current_debts',)),
 'stock':(('Ombor / vitrina · joriy','Склад / витрина · сейчас'),('stock','warehouses')),
 'movements':(('Ombor harakatlari','Движения склада'),('movements','product_events')),
 'clients':(('Mijozlar va qarz tarixi','Клиенты и история долга'),('clients','client_history','client_opening')),
 'suppliers':(('Ta’minotchilar va qarz tarixi','Поставщики и история долга'),('suppliers','supplier_entries','supplier_opening','supplier_balances','supplier_stock','supplier_sold')),
 'receipts':(('Kirim va partiyalar','Приходы и партии'),('receipts','supplier_lots','other_incomes')),
 'managers':(('Menejer puli','Деньги менеджера'),('manager_entries','manager_balances','manager_days')),
 'staff':(('Xodimlar, smena va jarimalar','Сотрудники, смены и штрафы'),('staff','shifts','fines')),
 'crm':(('CRM: vazifa va qo‘ng‘iroqlar','CRM: задачи и звонки'),('tasks','calls')),
 'quotes':(('KP','КП'),('quotes',)),
 'deliveries':(('Yetkazish','Доставки'),('deliveries',)),
 'website':(('Sayt katalogi va sinxronlash','Каталог сайта и синхронизация'),('website',)),
 'audit':(('Amallar tarixi','История действий'),('audit',)),
}
INTERNAL={'employee','id','source_id','ref','actor','owner','client','product','supplier','manager','sale','quote','receipt','receipt_id','lot','item','manager_entry','point_id','approved_by','cancelled_by','accepted_by','revision','priority','photos','gallery','file_id','token','token_hash','password','fingerprint'}

def categories():return [{'id':k,'uz':v[0][0],'ru':v[0][1]} for k,v in GROUPS.items()]

def sanitize(data):
    return {key:[{k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in row.items() if k not in INTERNAL and not k.endswith('_id') and not (k=='point' and isinstance(v,int))} for row in rows] for key,rows in data.items()}

def build(s,uid,q):
    s.director(uid);start=accounting_date(q.get('start',now()[:10]));end=accounting_date(q.get('end',now()[:10]))
    if start>end:raise ValueError('date')
    chosen=q.get('categories','all').split(',')
    if chosen==['all']:chosen=list(GROUPS)
    if not chosen or any(c not in GROUPS for c in chosen):raise ValueError('report_section')
    wanted={name for c in chosen for name in GROUPS[c][1]}
    with read_snapshot(s):
        data=s.report(uid,start,end)
        if any(key in chosen for key in ('product_analytics','employee_analytics')):
            from director_analytics import analytics
            analysis=analytics(s,uid,start,end)
            if 'product_analytics' in chosen:data['analytics_review']=[dict(currency=c,review_sales_count=count,note='Mahsulot qatorlarini tekshirish kerak / Требуется проверка строк товаров',as_of=analysis['as_of']) for c,count in sorted(analysis['review_by_currency'].items())]
            for key,source in [('product_analytics','products'),('employee_analytics','employees')]:
                if key in chosen:data[key]=[{**r,'as_of':analysis['as_of']} for r in analysis[source]]
        from director_sections import records
        for key in ('products','expenses','customer_returns','supplier_returns'):
            if key in chosen:
                data[key]=records(s,uid,key,start,end,q)
                if key=='customer_returns':
                    for row in data[key]:row.pop('items',None)
        if 'receipts' in chosen:data['other_incomes']=records(s,uid,'receipts',start,end,{'receipt_source':'movements'})
        if 'debts' in chosen:data['current_debts']=s.debts(uid)
        if 'stock' in chosen:data.update(s.inventory_report(uid))
        if 'clients' in chosen:
            clients=client_list(s,uid,q);data['clients']=clients;data['client_history']=[];data['client_opening']=[]
            for c in clients:
                card=client_card(s,uid,c['id'],start,end)
                data['client_history'] += [{**r,'client_name':c['name'],'history_review_count':card['history_review_count']} for r in card['ledger']['entries']]
                data['client_opening'] += [{**r,'client_name':c['name']} for r in card['ledger']['opening']]
        if 'suppliers' in chosen or 'receipts' in chosen:
            vendor=s.supplier_report(uid,start,end);data.update({'supplier_'+k:v for k,v in vendor.items() if k in ('stock','sold','balances','lots')})
            data['receipts']=s.rows('SELECT r.*,v.name supplier_name,p.name product_name FROM receipts r JOIN suppliers v ON v.id=r.supplier JOIN products p ON p.id=r.product WHERE r.date BETWEEN ? AND ?',(start,end))
            if 'suppliers' in chosen:
                data['suppliers']=s.suppliers(uid)['suppliers'];data['supplier_entries']=[];data['supplier_opening']=[]
                for v in data['suppliers']:
                    card=supplier_card(s,uid,v['id'],start,end)
                    for key,target in [('entries','supplier_entries'),('opening','supplier_opening')]:data[target]+=[{**r,'supplier_name':v['name']} for r in card['ledger'][key]]
        if 'managers' in chosen:
            a=s.manager_account(uid);data['manager_entries']=[r for r in a['entries'] if start<=r['date']<=end];data['manager_balances']=a['balances'];data['manager_days']=days(s,uid,start,end)
        if 'staff' in chosen:data['staff']=s.rows('SELECT id,name,role,active FROM users')
        if 'audit' in chosen:data['audit']=s.rows('SELECT a.created,a.action,u.name actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor WHERE substr(a.created,1,10) BETWEEN ? AND ?',(start,end))
        if 'website' in chosen:data['website']=s.rows('SELECT p.name,p.brand,p.size,w.published,w.category,w.price_cents,w.price_mode,o.version,o.delivered_version,o.last_success,o.last_error FROM products p LEFT JOIN website_products w ON w.product=p.id JOIN catalog_outbox o ON o.product=p.id')
        data={k:filtered(v,q) for k,v in data.items() if k in wanted}
        # Resolve references before removing all internal identifiers.
        enriched=Bot.enrich(SimpleNamespace(s=s),data)
        for rows in enriched.values():
            for r in rows:
                for key,table,dest in [('supplier','suppliers','supplier_name'),('manager','users','manager_name'),('product','products','product_name')]:
                    if r.get(key) is not None and dest not in r:r[dest]=(s.supplier_row(r[key]) if table=='suppliers' else s.one(table,r[key]))['name']
        current={'products','stock','warehouses','current_debts','clients','suppliers','supplier_balances','supplier_stock','supplier_lots','manager_balances','staff','tasks','website'}
        stamp=now()
        for key,rows in enriched.items():
            if key in current:
                for row in rows:row['as_of']=stamp
        return sanitize(enriched)
