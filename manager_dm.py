"""Personal money notices for each manager, in the manager's own private chat with the bot.

The director group (topic_notices) shows every manager's money moves together. A manager who
wants to count "how much did I give / how much do I hold" gets confused by other managers'
messages there, so each manager also gets their OWN moves only, with the balance after the move,
in their private chat with the bot. Nobody else's money appears in it.

Source of truth is the audit log, like topic_notices; it has its own cursor and never back-fills
history. On by default; set NOTIFY_MANAGER_DM=0 to turn it off.
"""
import json
import os
from core import fmt

ACTIONS = ('manager_fund', 'manager_received', 'manager_expense', 'manager_return',
           'manager_handover_requested', 'manager_handover_accepted', 'manager_handover_rejected',
           'manager_day_closed')
CURSOR = 'manager_dm_cursor'
LIMIT = 200

TITLES = {
    'manager_fund': ('🔁 Sizga pul berildi', '🔁 Вам выданы деньги'),
    'manager_received': ('🔁 Sizdan pul qabul qilindi', '🔁 От вас приняты деньги'),
    'manager_expense': ('📤 Chiqim yozildi', '📤 Записан расход'),
    'manager_return': ('🔁 Pul topshirish so‘rovi yuborildi', '🔁 Отправлен запрос на сдачу денег'),
    'manager_handover_requested': ('🔁 Pul topshirish so‘rovi yuborildi', '🔁 Отправлен запрос на сдачу денег'),
    'manager_handover_accepted': ('✅ Topshirgan pulingiz qabul qilindi', '✅ Сданные деньги приняты'),
    'manager_handover_rejected': ('❌ Topshirgan pulingiz rad etildi', '❌ Сдача денег отклонена'),
    'manager_day_closed': ('🔒 Kuningiz yopildi', '🔒 Ваш день закрыт'),
}


def enabled():
    return os.environ.get('NOTIFY_MANAGER_DM', '1').strip().lower() not in ('0', 'false', 'no', 'off', '')


def _entry(s, action, ref):
    """(manager_id, amount, currency, extra_line) for one audit row, or None."""
    q = lambda sql: s.db.execute(sql, (ref,)).fetchone()
    if action == 'manager_received':
        r = q('SELECT manager,amount,currency,note FROM manager_received WHERE id=?')
    elif action == 'manager_day_closed':
        r = q('SELECT manager,date FROM manager_day_closings WHERE id=?')
        return (r['manager'], None, None, r['date']) if r else None
    elif action == 'manager_handover_rejected':
        r = q('SELECT e.manager,e.amount,e.currency,h.reject_reason note FROM manager_entries e '
              'JOIN manager_return_receipts h ON h.entry=e.id WHERE e.id=?')
    else:
        r = q('SELECT manager,amount,currency,note FROM manager_entries WHERE id=?')
    return (r['manager'], r['amount'], r['currency'], r['note']) if r else None


def build(s, action, ref, created):
    """(chat_id, text) for the manager this row is about, or None."""
    found = _entry(s, action, ref)
    if not found:
        return None
    manager, amount, currency, extra = found
    user = s.db.execute('SELECT lang,active FROM users WHERE id=?', (manager,)).fetchone()
    if not user or not user['active']:
        return None
    ru = user['lang'] == 'ru'
    lines = [TITLES[action][ru]]
    if amount is not None:
        lines.append(f'{"Сумма" if ru else "Summa"}: {fmt(amount)} {currency}')
    if extra:
        lines.append(' '.join(str(extra).split())[:200])
    from manager_money import account
    # The manager's own account only: other managers' money never enters this message.
    for b in account(s, manager, manager)['balances']:
        if currency and b['currency'] != currency:
            continue
        lines.append(f'{"Остаток у вас" if ru else "Sizdagi qoldiq"}: {fmt(b["balance"])} {b["currency"]}')
        if b['pending_return']:
            lines.append(f'{"Ждёт подтверждения" if ru else "Tasdiq kutmoqda"}: {fmt(b["pending_return"])} {b["currency"]}')
    lines.append(str(created)[:16].replace('T', ' '))
    return manager, '\n'.join(lines)


def poll(s):
    """Queue personal notices for audit rows newer than the stored cursor. Safe every loop."""
    last = s.db.execute('SELECT value FROM meta WHERE key=?', (CURSOR,)).fetchone()
    top = s.db.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0]
    if last is None or not enabled():
        with s.db:
            s.db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (CURSOR, str(top)))
        return 0
    cursor = int(last[0])
    if top <= cursor:
        return 0
    rows = s.db.execute('SELECT * FROM audit WHERE id>? AND id<=? ORDER BY id LIMIT ?', (cursor, top, LIMIT)).fetchall()
    queued = 0
    with s.db:
        for row in rows:
            if row['action'] in ACTIONS and row['ref'] is not None:
                try:
                    found = build(s, row['action'], row['ref'], row['created'])
                except Exception:
                    found = None
                if found:
                    chat, text = found
                    s.db.execute('INSERT INTO outbox(chat,payload) VALUES(?,?)', (chat, json.dumps({'text': text[:4000]}, ensure_ascii=False)))
                    queued += 1
            cursor = row['id']
        s.db.execute('UPDATE meta SET value=? WHERE key=?', (str(cursor), CURSOR))
    return queued
