"""Director-controlled employee invitations; callers own the write transaction."""
import hashlib
import re
import secrets
import time
import json

PERMISSIONS = {
    "catalog": ("Katalog va qoldiq", "Каталог и остатки"),
    "sales": ("Sotuvlar", "Продажи"),
    "clients": ("Mijozlar", "Клиенты"),
    "debts": ("Qarz va to‘lovlar", "Долги и оплаты"),
    "quotes": ("Tijorat takliflari", "Коммерческие предложения"),
    "calls": ("Qo‘ng‘iroqlar", "Звонки"),
    "tasks": ("Vazifalar", "Задачи"),
    "delivery": ("Labo yetkazish", "Доставка Labo"),
    "attendance": ("Ish kuni", "Рабочий день"),
    "reports": ("Excel hisobot", "Отчёт Excel"),
    "income": ("Mahsulot kirimi", "Приход товара"),
}
COMMANDS = {
 "stock":"catalog", "photo":"catalog", "catalog":"catalog", "product_photo":"catalog", "product_photo_delete":"catalog",
 "sell":"sales", "sales":"sales", "clients":"clients", "newclient":"clients", "client":"clients", "card":"clients",
 "collect_debt":"debts", "pay":"debts", "debt_due":"debts", "debts":"debts", "overdue":"debts",
 "quote":"quotes", "quotes":"quotes", "pdf":"quotes", "quote_options":"quotes", "quote_status":"quotes",
 "call":"calls", "task":"tasks", "tasks":"tasks", "done":"tasks",
 "delivery":"delivery", "delivery_status":"delivery", "delivery_fee_collect":"delivery", "driver_deliveries":"delivery",
 "startwork":"attendance", "endwork":"attendance", "report":"reports", "summary":"reports",
 "income":"income", "income_product":"income", "return":"income", "supplier_income":"income", "supplier_payment":"income",
}
DEFAULT_PERMISSIONS = list(PERMISSIONS)

def permissions(store, uid):
    user=store.user(uid);role=effective_role(store,uid)
    if role=='driver':return ['delivery']
    return [key for key in PERMISSIONS if role!='director' or key!='attendance']


def effective_role(store,uid):
    user=store.user(uid)
    row=store.db.execute('SELECT managed_role FROM staff_access WHERE user_id=?',(uid,)).fetchone()
    return row['managed_role'] if row and row['managed_role'] in ('director','employee','driver') else user['role']


def require_command(store, uid, cmd):
    store.user(uid)
    if effective_role(store,uid)=='driver' and cmd not in {'language','delivery_status','delivery_fee_collect','driver_deliveries'}:
        raise PermissionError()
    if cmd in {'director_client_save','supplier_save','supplier_archive','supplier_new','supplier_edit','suppliers','supplier_report','supplier_return','point_kind','point_archive','transfer','manager_fund','document_extract','document_preview','document_import','excel_preview','excel_import','staff','staff_invite','staff_set','staff_cancel_invite','staff_role','newpoint','point','newproduct','product','editproduct','minimum','opening_stock','fine','writeoff','cancel_sale','lowstock'}:
        store.director(uid)
    permission=COMMANDS.get(cmd)
    if permission and permission not in permissions(store,uid): raise PermissionError()



class StaffAccess:
    def __init__(self, store):
        self.s = store

    def pending(self):
        return self.s.rows("SELECT id,label,expires,role FROM staff_invites WHERE status='pending' AND expires>? AND created_by IN (SELECT id FROM users WHERE active=1 AND role='director') ORDER BY id DESC", (int(time.time()),))

    def occupied(self):
        active = self.s.db.execute("SELECT COUNT(*) FROM users WHERE active=1 AND role='employee'").fetchone()[0]
        return active + len(self.pending())

    def team(self, uid):
        self.s.director(uid)
        return {'employees': self.s.rows("SELECT u.id,u.name,u.active,CASE WHEN sa.managed_role IN ('employee','director','driver') THEN sa.managed_role ELSE u.role END role FROM users u LEFT JOIN staff_access sa ON sa.user_id=u.id ORDER BY u.active DESC,role,u.name,u.id"), 'invites': self.pending(), 'limit': None}

    def validate_role(self,role):
        if role not in ('employee','director','driver'):raise ValueError('staff_target')

    def director_capacity(self,exclude=None):
        active=self.s.db.execute("SELECT COUNT(*) FROM users WHERE active=1 AND role='director' AND id<>?",(exclude or -1,)).fetchone()[0]
        reserved=sum(r['role']=='director' for r in self.pending())
        if active+reserved>=3:raise ValueError('director_limit')

    def assign_role(self,uid,employee,role):
        self.s.director(uid);self.validate_role(role)
        target=self.s.one('users',employee)
        old_role=effective_role(self.s,employee)
        if employee==uid and role!=old_role:raise ValueError('staff_self')
        if role=='director' and old_role!='director' and target['active']:self.director_capacity()
        self.s.db.execute('INSERT INTO staff_access(user_id,active,managed_role) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET managed_role=excluded.managed_role',(employee,target['active'],role))
        self.s.db.execute('UPDATE users SET role=? WHERE id=?',('employee' if role=='driver' else role,employee))
        self.s.db.execute('DELETE FROM sessions WHERE user_id=?',(employee,))
        self.s.db.execute('DELETE FROM ui_views WHERE user_id=?',(employee,))
        self.s.log(uid,'staff_role',employee)
        return employee


    def invite(self, uid, label, username, role="employee"):
        self.validate_role(role)
        self.s.director(uid)
        if not isinstance(label, str) or not 1<=len(label.strip())<=100:
            raise ValueError('text')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', username or ''):
            raise ValueError('bot_username')
        if role=="director":self.director_capacity()
        token = secrets.token_urlsafe(24)
        ref = self.s.add('staff_invites', token_hash=hashlib.sha256(token.encode()).hexdigest(), label=label.strip(), role=role, created_by=uid, expires=int(time.time())+86400)
        self.s.log(uid, 'staff_invite', ref)
        return {'invite_id': ref, 'url': f'https://t.me/{username}?start=staff_{token}'}

    def cancel(self, uid, ref):
        self.s.director(uid)
        cur = self.s.db.execute("UPDATE staff_invites SET status='revoked' WHERE id=? AND status='pending'", (ref,))
        if not cur.rowcount:
            raise ValueError('invite_invalid')
        self.s.log(uid, 'staff_invite_cancel', ref)
        return ref

    def set_active(self, uid, employee, active):
        self.s.director(uid)
        target = self.s.one('users', employee)
        if type(active) is not bool:
            raise ValueError('staff_target')
        if employee==uid and not active:raise ValueError('staff_self')
        if active and not target['active'] and target['role']=='director':self.director_capacity()
        self.s.db.execute('INSERT INTO staff_access(user_id,active) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET active=excluded.active', (employee, int(active)))
        self.s.db.execute('UPDATE users SET active=? WHERE id=?', (int(active), employee))
        if not active:
            self.s.db.execute('DELETE FROM sessions WHERE user_id=?', (employee,))
            self.s.db.execute('DELETE FROM ui_views WHERE user_id=?', (employee,))
        self.s.log(uid, 'staff_enable' if active else 'staff_disable', employee)
        return employee

    def accept(self, token, uid, name):
        if type(uid) is not int or not 0<uid<=2**53 or not re.fullmatch(r'[A-Za-z0-9_-]{32}', token or ''):
            raise ValueError('invite_invalid')
        row = self.s.db.execute("SELECT * FROM staff_invites WHERE token_hash=? AND status='pending' AND expires>?", (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if not row:
            raise ValueError('invite_invalid')
        self.s.director(row['created_by'])
        # A disabled account cannot bypass suspension by obtaining another link.
        if self.s.db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
            raise ValueError('staff_registered')
        self.validate_role(row['role'])
        if row['role']=='director':
            # This invitation already reserves its director seat.
            if self.s.db.execute("SELECT COUNT(*) FROM users WHERE active=1 AND role='director'").fetchone()[0]>=3:raise ValueError('director_limit')
        self.s.add('users', id=uid, role='employee' if row['role']=='driver' else row['role'], name=(name.strip() or str(uid))[:150])
        self.s.add('staff_access', user_id=uid, active=1, managed_role=row['role'])
        self.s.db.execute("UPDATE staff_invites SET status='used',joined_by=? WHERE id=?", (uid, row['id']))
        self.s.log(uid, 'staff_join', row['id'])
        return row['id']

