"""Named director sections over existing immutable business records. No new ledger."""
from manager_money import read_snapshot

KINDS={'products','expenses','customer_returns','supplier_returns','receipts'}


def records(s,uid,kind,start,end,q):
    s.director(uid)
    with read_snapshot(s):
        if kind=='products':
            rows=s.rows('SELECT id,name,brand,size,price,currency,price_pending,active FROM products ORDER BY id DESC')
            for r in rows:
                if r['price_pending']:r['price']=None
            return rows
        if kind=='expenses':
            return s.rows("SELECT e.*,u.name manager_name,a.name actor_name,v.name supplier_name,x.supplier,x.method FROM manager_entries e JOIN users u ON u.id=e.manager JOIN users a ON a.id=e.actor LEFT JOIN supplier_entries x ON x.manager_entry=e.id LEFT JOIN suppliers v ON v.id=x.supplier WHERE e.kind='expense' AND e.date BETWEEN ? AND ? ORDER BY e.date DESC,e.id DESC",(start,end))
        if kind=='customer_returns':
            rows=s.rows("SELECT s.id,s.client,c.name client_name,s.actor,u.name manager_name,s.total,s.paid,s.currency,s.status,s.created sale_date,s.cancelled_at created,s.cancel_reason reason,s.cancelled_by,a.name actor_name,COALESCE(r.amount,0) amount FROM sales s JOIN clients c ON c.id=s.client JOIN users u ON u.id=s.actor LEFT JOIN users a ON a.id=s.cancelled_by LEFT JOIN refunds r ON r.sale=s.id WHERE s.status='cancelled' AND substr(s.cancelled_at,1,10) BETWEEN ? AND ? ORDER BY s.cancelled_at DESC,s.id DESC",(start,end))
            for r in rows:
                r['items']=s.rows('SELECT i.name,i.qty,i.price,t.name point_name FROM sale_items i JOIN points t ON t.id=COALESCE(i.point,?) WHERE i.sale=?',(s.one('sales',r['id'])['point'],r['id']))
                for item in r['items']:item['currency']=r['currency']
                r['product_name']=', '.join(i['name']+' × '+str(i['qty']) for i in r['items'])
            return rows
        if kind=='supplier_returns':
            return s.rows("SELECT e.*,v.name supplier_name,p.name product_name,t.name point_name,l.point point_id,r.cost,u.name actor_name FROM supplier_entries e JOIN suppliers v ON v.id=e.supplier JOIN inventory_lots l ON l.id=e.lot JOIN receipts r ON r.id=e.receipt JOIN products p ON p.id=l.product JOIN points t ON t.id=l.point JOIN users u ON u.id=e.actor WHERE e.kind='return' AND e.date BETWEEN ? AND ? ORDER BY e.date DESC,e.id DESC",(start,end))
        if kind=='receipts':
            source=q.get('receipt_source','supplier')
            if source not in ('supplier','movements'):raise ValueError('route')
            if source=='movements':
                # Supplier receipts already have their own view; never count them twice.
                return s.rows("SELECT m.*,substr(m.created,1,10) date,p.name product_name,p.brand,p.size,t.name point_name,m.point point_id,u.name actor_name FROM movements m JOIN products p ON p.id=m.product JOIN points t ON t.id=m.point JOIN users u ON u.id=m.actor WHERE m.kind IN ('in','opening','excel_income') AND substr(m.created,1,10) BETWEEN ? AND ? ORDER BY m.id DESC",(start,end))
            rows=s.rows('SELECT r.*,r.qty*r.cost amount,p.name product_name,v.name supplier_name,u.name actor_name FROM receipts r JOIN products p ON p.id=r.product JOIN suppliers v ON v.id=r.supplier JOIN users u ON u.id=r.actor WHERE r.date BETWEEN ? AND ? ORDER BY r.date DESC,r.id DESC',(start,end))
            for r in rows:r['lots']=s.rows('SELECT t.name point_name,l.qty FROM inventory_lots l JOIN points t ON t.id=l.point WHERE l.receipt=? ORDER BY l.id',(r['id'],))
            return rows
    raise ValueError('route')
