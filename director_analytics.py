"""Two director-only sale analyses. Exact cents; no guessed debt/cost allocation."""
from accounting import accounting_date
from core import now
from manager_money import read_snapshot

MONEY={'revenue','paid_to_date','debt_to_date'}


def line_amount(row):
    qty,price,discount=row['qty'],row['price'],row['discount']
    if any(type(v) is not int for v in (qty,price,discount)) or qty<=0 or price<0 or not 0<=discount<=100:return None
    # Same half-even cent rounding as the original Store.items Decimal quantize.
    cents,remainder=divmod(price*qty*(100-discount),100)
    return cents+int(remainder>50 or remainder==50 and cents%2==1)


def analytics(s,uid,start,end):
    s.director(uid);start=accounting_date(start);end=accounting_date(end)
    if start>end:raise ValueError('date')
    with read_snapshot(s):
        sales=s.rows("SELECT s.id,s.actor,s.client,s.total,s.paid,s.currency,u.name employee_name,u.active FROM sales s JOIN users u ON u.id=s.actor WHERE s.status='active' AND substr(s.created,1,10) BETWEEN ? AND ? ORDER BY s.id",(start,end))
        lines=s.rows("SELECT i.*,p.name product_name FROM sale_items i JOIN sales s ON s.id=i.sale JOIN products p ON p.id=i.product WHERE s.status='active' AND substr(s.created,1,10) BETWEEN ? AND ? ORDER BY i.sale,i.id",(start,end))
        by_sale={}
        for row in lines:by_sale.setdefault(row['sale'],[]).append(row)
        products={};employees={};review=0;reviews={}
        for sale in sales:
            items=by_sale.get(sale['id'],[]);amounts=[line_amount(i) for i in items]
            valid=bool(items) and all(v is not None for v in amounts) and sum(amounts)==sale['total']
            currency=sale['currency']
            if not valid:review+=1;reviews[currency]=reviews.get(currency,0)+1
            e=employees.setdefault((sale['actor'],currency),dict(employee=sale['actor'],employee_name=sale['employee_name'],active=sale['active'],currency=currency,sales_count=0,client_count=0,qty=0,revenue=0,paid_to_date=0,debt_to_date=0,_clients=set()))
            e['sales_count']+=1;e['_clients'].add(sale['client']);e['revenue']+=sale['total'];e['paid_to_date']+=sale['paid'];e['debt_to_date']+=sale['total']-sale['paid']
            known_qty=bool(items) and all(type(i['qty']) is int and i['qty']>0 for i in items)
            e['qty']=e['qty']+sum(i['qty'] for i in items) if known_qty and e['qty'] is not None else None
            seen=set()
            for item,amount in zip(items,amounts):
                key=(item['product'],currency);p=products.setdefault(key,dict(product=item['product'],product_name=item['product_name'],currency=currency,qty=0,sales_count=0,revenue=0,unknown_sales_count=0))
                p['qty']=p['qty']+item['qty'] if p['qty'] is not None and type(item['qty']) is int and item['qty']>0 else None
                if key not in seen:p['sales_count']+=1;p['unknown_sales_count']+=int(not valid);seen.add(key)
                p['revenue']=p['revenue']+amount if valid and p['revenue'] is not None else None
        for row in employees.values():row['client_count']=len(row.pop('_clients'))
        return dict(start=start,end=end,as_of=now(),review_sales_count=review,review_by_currency=reviews,products=sorted(products.values(),key=lambda r:(r['currency'],r['product'])),employees=sorted(employees.values(),key=lambda r:(r['currency'],r['employee'])))


def for_api(data):
    """Cents as decimal strings prevent JSON/JavaScript integer precision loss."""
    return {**data,**{key:[{k:str(v) if k in MONEY and v is not None else v for k,v in row.items()} for row in data[key]] for key in ('products','employees')}}
