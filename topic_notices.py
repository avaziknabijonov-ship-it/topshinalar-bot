"""Optional category notices (prixod / kassa / o'tkazma) for ONE private director group.

Source of truth is the existing audit log: new audit rows are turned into short messages and
queued in the same durable outbox the bot already uses. Nothing is sent unless a destination
is configured in the environment, and history is never back-filled.

Environment (all optional, empty = that category is off):
  NOTIFY_PRIXOD, NOTIFY_KASSA, NOTIFY_OTKAZMA = "<group_chat_id>" or "<group_chat_id>:<topic_id>"
  NOTIFY_LANG = uz | ru   (default uz)
"""
import json
import logging
import os
import re
import time
from core import fmt

CATEGORIES = ('prixod', 'kassa', 'otkazma')
ROUTE_KEY = 'route'
# audit action -> category
ACTIONS = {
    'supplier_income': 'prixod', 'supplier_return': 'prixod',
    'sale': 'kassa', 'payment': 'kassa', 'sale_cancel': 'kassa', 'supplier_payment': 'kassa',
    'delivery_fee_collect': 'kassa', 'manager_expense': 'kassa',
    'manager_fund': 'otkazma', 'manager_return': 'otkazma', 'manager_received': 'otkazma',
    'manager_handover_requested': 'otkazma', 'manager_handover_accepted': 'otkazma',
    'manager_handover_rejected': 'otkazma', 'manager_day_closed': 'otkazma',
}
LIMIT = 200


def destination(category):
    """(chat_id, topic_id|None) or None. Group IDs are negative; topic IDs are positive."""
    value = os.environ.get('NOTIFY_' + category.upper(), '').strip()
    match = re.fullmatch(r'(-\d{5,16})(?::([1-9]\d{0,9}))?', value)
    if not match:
        return None
    return int(match.group(1)), (int(match.group(2)) if match.group(2) else None)


def configured():
    return {c: d for c in CATEGORIES if (d := destination(c))}


def _name(value):
    return ' '.join(str(value or '').split())[:120] or '—'


def _user(s, uid):
    row = s.db.execute('SELECT name FROM users WHERE id=?', (uid,)).fetchone()
    return _name(row['name'] if row else uid)


def _t(ru, uz, rus):
    return rus if ru else uz


def build(s, action, ref, actor, created, ru=False):
    """Message text for one audit row, or None when the row is not worth posting."""
    q = lambda sql, *a: s.db.execute(sql, a).fetchone()
    who = _user(s, actor)
    stamp = str(created)[:16].replace('T', ' ')
    tail = f'\n{_t(ru, "Kim", "Кто")}: {who}\n{stamp}'
    if action == 'sale':
        r = q('SELECT s.total,s.paid,s.currency,s.payment,c.name client FROM sales s JOIN clients c ON c.id=s.client WHERE s.id=?', ref)
        if not r or r['paid'] <= 0:
            return None  # a sale fully on credit is not a cash receipt
        return (f'🧾 {_t(ru, "Savdo tushumi", "Выручка с продажи")} #{ref}\n{_t(ru, "Mijoz", "Клиент")}: {_name(r["client"])}\n'
                f'{_t(ru, "Tushdi", "Получено")}: {fmt(r["paid"])} {r["currency"]} ({_name(r["payment"])})\n'
                f'{_t(ru, "Jami", "Итого")}: {fmt(r["total"])} {r["currency"]}\n{_t(ru, "Qarz", "Долг")}: {fmt(r["total"] - r["paid"])} {r["currency"]}' + tail)
    if action == 'payment':
        r = q('SELECT p.amount,p.method,p.currency,s.id sale,s.total-s.paid debt,c.name client FROM payments p JOIN sales s ON s.id=p.sale JOIN clients c ON c.id=s.client WHERE p.id=?', ref)
        if not r:
            return None
        return (f'💵 {_t(ru, "Qarz to‘lovi", "Оплата долга")} (#{r["sale"]})\n{_t(ru, "Mijoz", "Клиент")}: {_name(r["client"])}\n'
                f'{_t(ru, "Tushdi", "Получено")}: {fmt(r["amount"])} {r["currency"]} ({_name(r["method"])})\n'
                f'{_t(ru, "Qolgan qarz", "Остаток долга")}: {fmt(r["debt"])} {r["currency"]}' + tail)
    if action == 'sale_cancel':
        r = q('SELECT s.currency,COALESCE(f.amount,0) refund FROM sales s LEFT JOIN refunds f ON f.sale=s.id WHERE s.id=?', ref)
        if not r:
            return None
        return f'↩️ {_t(ru, "Sotuv bekor qilindi", "Продажа отменена")} #{ref}\n{_t(ru, "Qaytarildi", "Возвращено")}: {fmt(r["refund"])} {r["currency"]}' + tail
    if action == 'supplier_payment':
        r = q('SELECT e.amount,e.currency,e.method,v.name supplier FROM supplier_entries e JOIN suppliers v ON v.id=e.supplier WHERE e.id=?', ref)
        if not r:
            return None
        return f'📤 {_t(ru, "Yetkazib beruvchiga to‘lov", "Оплата поставщику")}\n{_name(r["supplier"])}: {fmt(r["amount"])} {r["currency"]} ({_name(r["method"])})' + tail
    if action == 'delivery_fee_collect':
        return f'🚚 {_t(ru, "Yetkazish haqi olindi", "Получена оплата доставки")} #{ref}' + tail
    if action in ('manager_expense', 'manager_fund', 'manager_return'):
        r = q('SELECT e.amount,e.currency,e.note,u.name manager FROM manager_entries e JOIN users u ON u.id=e.manager WHERE e.id=?', ref)
        if not r:
            return None
        title = {'manager_expense': ('📤 Chiqim', '📤 Расход'), 'manager_fund': ('🔁 Kassaga pul berildi', '🔁 Выдано в подотчёт'),
                 'manager_return': ('🔁 Pul topshirildi', '🔁 Деньги сданы')}[action]
        return f'{title[ru]}\n{_t(ru, "Mas’ul", "Ответственный")}: {_name(r["manager"])}\n{fmt(r["amount"])} {r["currency"]}' + (f'\n{_name(r["note"])}' if r['note'] else '') + tail
    if action == 'manager_received':
        r = q('SELECT e.amount,e.currency,u.name manager FROM manager_received e JOIN users u ON u.id=e.manager WHERE e.id=?', ref)
        if not r:
            return None
        return f'🔁 {_t(ru, "Pul qabul qilindi", "Деньги получены")}\n{_name(r["manager"])}: {fmt(r["amount"])} {r["currency"]}' + tail
    if action.startswith('manager_handover') or action == 'manager_day_closed':
        r = q('SELECT e.amount,e.currency,u.name manager FROM manager_entries e JOIN users u ON u.id=e.manager WHERE e.id=?', ref) if action != 'manager_day_closed' else None
        titles = {'manager_handover_requested': ('🔁 Topshirish so‘rovi', '🔁 Запрос на сдачу'), 'manager_handover_accepted': ('✅ Topshirish qabul qilindi', '✅ Сдача принята'),
                  'manager_handover_rejected': ('❌ Topshirish rad etildi', '❌ Сдача отклонена'), 'manager_day_closed': ('🔒 Kun yopildi', '🔒 День закрыт')}
        body = f'\n{_name(r["manager"])}: {fmt(r["amount"])} {r["currency"]}' if r else ''
        return titles[action][ru] + body + tail
    if action == 'supplier_income':
        r = q('SELECT r.qty,r.cost,r.currency,p.name product,v.name supplier FROM receipts r JOIN products p ON p.id=r.product JOIN suppliers v ON v.id=r.supplier WHERE r.id=?', ref)
        if not r:
            return None
        return (f'📥 {_t(ru, "Prixod", "Приход")} #{ref}\n{_name(r["product"])}\n{_t(ru, "Soni", "Кол-во")}: {r["qty"]} × {fmt(r["cost"])} {r["currency"]}\n'
                f'{_t(ru, "Yetkazib beruvchi", "Поставщик")}: {_name(r["supplier"])}' + tail)
    if action == 'supplier_return':
        r = q('SELECT e.qty,e.amount,e.currency,p.name product,v.name supplier FROM supplier_entries e JOIN suppliers v ON v.id=e.supplier JOIN receipts r ON r.id=e.receipt JOIN products p ON p.id=r.product WHERE e.id=?', ref)
        if not r:
            return None
        return f'📤 {_t(ru, "Yetkazib beruvchiga qaytarildi", "Возврат поставщику")}\n{_name(r["product"])} × {r["qty"]}\n{_name(r["supplier"])}: {fmt(r["amount"])} {r["currency"]}' + tail
    return None


def poll(s):
    """Queue notices for audit rows newer than the stored cursor. Safe to call every loop."""
    routes = configured()
    last = s.db.execute("SELECT value FROM meta WHERE key='topic_notice_cursor'").fetchone()
    top = s.db.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0]
    if last is None or not routes:
        # First run, or the feature is off: start from "now" so enabling it never floods history.
        with s.db:
            s.db.execute("INSERT INTO meta(key,value) VALUES('topic_notice_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(top),))
        return 0
    cursor = int(last[0])
    if top <= cursor:
        return 0
    ru = os.environ.get('NOTIFY_LANG', 'uz').strip().lower() == 'ru'
    rows = s.db.execute('SELECT * FROM audit WHERE id>? ORDER BY id LIMIT ?', (cursor, LIMIT)).fetchall()
    queued = 0
    with s.db:
        for row in rows:
            category = ACTIONS.get(row['action'])
            if category in routes and row['ref'] is not None:
                try:
                    text = build(s, row['action'], row['ref'], row['actor'], row['created'], ru)
                except Exception:
                    text = None
                if text:
                    chat, topic = routes[category]
                    payload = {'text': text[:4000], ROUTE_KEY: category}
                    if topic:
                        payload['message_thread_id'] = topic
                    s.db.execute('INSERT INTO outbox(chat,payload) VALUES(?,?)', (chat, json.dumps(payload, ensure_ascii=False)))
                    queued += 1
            cursor = row['id']
        s.db.execute("UPDATE meta SET value=? WHERE key='topic_notice_cursor'", (str(cursor),))
    return queued


_checked = {}


def allowed(s, api, row_chat, payload):
    """Delivery guard for routed rows. True = send, False = drop this row.

    The configured destination must still match and the group must contain nobody but the
    bot and active directors (member count check), so a leaked invite link cannot read money.
    """
    category = payload.get(ROUTE_KEY)
    if category not in CATEGORIES:
        return False
    dest = destination(category)
    if not dest or dest[0] != row_chat or dest[1] != payload.get('message_thread_id'):
        return False
    hit = _checked.get(row_chat)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    # A Telegram outage raises here, so the row stays queued and is retried; only a definite
    # "not safe" answer drops it.
    chat = api.call('getChat', {'chat_id': row_chat})
    count = api.call('getChatMemberCount', {'chat_id': row_chat})
    directors = s.db.execute("SELECT COUNT(*) FROM users WHERE role='director' AND active=1").fetchone()[0]
    ok = chat.get('type') in ('group', 'supergroup') and 1 <= count <= directors + 1
    _checked[row_chat] = (time.time(), ok)
    if not ok:
        logging.warning('Notice group %s skipped: it must be a private group with only the bot and active directors', row_chat)
    return ok
