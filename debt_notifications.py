"""Durable director notices for newly recorded debt payments, using bot outbox."""
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from accounting import transaction,atomic


def migrate(s):
    # Existing outbox layout is shared with Bot.queue; never change old migrations.
    with s.db,transaction(s):
        s.db.execute('CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,chat INTEGER NOT NULL,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0)')
        s.db.execute('''CREATE TABLE IF NOT EXISTS debt_payment_notifications(
            payment INTEGER PRIMARY KEY REFERENCES payments(id),
            director INTEGER NOT NULL REFERENCES users(id),
            outbox_id INTEGER UNIQUE REFERENCES outbox(id) ON DELETE SET NULL,
            state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','sent','skipped')),
            created TEXT NOT NULL)''')


def name(value,lang):
    text=' '.join(str(value or '').split())[:200]
    return text if text and not text.isdigit() else ('Имя не указано' if lang=='ru' else 'Ism kiritilmagan')


def recipient(s):
    """Exactly one explicit private director destination; no broadcast/default."""
    value=os.environ.get('DIRECTOR_DEBT_CHAT_ID','').strip()
    if not re.fullmatch(r'[1-9]\d{0,15}',value) or int(value)>2**53:return None
    try:user=s.user(int(value))
    except (ValueError,PermissionError):return None
    return user if user['role']=='director' else None


@atomic
def enqueue(s,payment):
    """Only during a new Store.payment, never backfill historical payments."""
    from core import fmt
    director=recipient(s)
    if director is None or s.db.execute('SELECT 1 FROM debt_payment_notifications WHERE payment=?',(payment,)).fetchone():return
    row=s.db.execute('''SELECT p.*,c.name client_name,u.name collector_name,s.total-s.paid debt
        FROM payments p JOIN sales s ON s.id=p.sale JOIN clients c ON c.id=s.client
        JOIN users u ON u.id=p.actor WHERE p.id=?''',(payment,)).fetchone()
    if row is None:raise ValueError('missing')
    lang=director['lang'];ru=lang=='ru';currency=row['currency']
    title=('✅ Клиент погасил долг' if ru else '✅ Mijoz qarzini to‘ladi') if row['debt']==0 else ('💵 Клиент оплатил часть долга' if ru else '💵 Mijoz qarzidan to‘lov')
    method={'naqd':('Naqd','Наличные'),'karta':('Karta','Карта'),'perechisleniya':('Bank','Банк')}.get(row['method'],(row['method'],row['method']))[ru]
    try:stamp=datetime.fromisoformat(row['created']).astimezone(ZoneInfo('Asia/Tashkent')).strftime('%d.%m.%Y %H:%M:%S')
    except ValueError:stamp=row['created']
    fields=[('Mijoz','Клиент',name(row['client_name'],lang)),('To‘landi','Оплачено',fmt(row['amount'])+' '+currency),('To‘lovdan keyingi qarz','Долг после оплаты',fmt(row['debt'])+' '+currency),('Kim tomonidan','Кто принял',name(row['collector_name'],lang)),('Usul','Способ',method),('Sana','Дата',stamp)]
    text=title+'\n'+'\n'.join((b if ru else a)+': '+str(v) for a,b,v in fields)
    ref=s.add('outbox',chat=director['id'],payload=json.dumps({'text':text},ensure_ascii=False))
    s.db.execute('INSERT INTO debt_payment_notifications(payment,director,outbox_id,created) VALUES(?,?,?,?)',(payment,director['id'],ref,row['created']))


def may_deliver(s,outbox_id,chat):
    row=s.db.execute('SELECT director,state FROM debt_payment_notifications WHERE outbox_id=?',(outbox_id,)).fetchone()
    if row is None:return True
    if row['director']!=chat or row['state']!='queued':return False
    user=recipient(s)
    return user is not None and user['id']==chat


def finish(s,outbox_id,state):
    s.db.execute("UPDATE debt_payment_notifications SET state=? WHERE outbox_id=? AND state='queued'",(state,outbox_id))
