"""Own-invoice debt collection, reusing Store.payment and its single receipt ledger."""
import re
from accounting import atomic
from core import integer


@atomic
def collect(s,uid,data):
    s.user(uid);sale=s.one('sales',integer(data.get('sale')));s.own(uid,sale)
    expected=data.get('expected_paid')
    if isinstance(expected,bool) or not re.fullmatch(r'\d{1,17}',str(expected)) or int(expected)>10**16:raise ValueError('sale_changed')
    if sale['paid']!=int(expected):raise ValueError('debt_changed')
    # Currency, collector and timestamp always come from server records/session.
    method=str(data.get('payment',''));method={'transfer':'perechisleniya'}.get(method,method)
    ref=s.payment(uid,sale['id'],str(data.get('amount','')),method,expected_paid=int(expected))
    row=s.rows('SELECT amount,currency,created FROM payments WHERE id=?',(ref,))[0]
    after=s.one('sales',sale['id'])
    return dict(payment=ref,sale=sale['id'],amount_cents=str(row['amount']),remaining_cents=str(after['total']-after['paid']),currency=row['currency'],created=row['created'],collector_name=s.user(uid)['name'])
