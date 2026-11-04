"""Browser-bound, one-use Telegram approval and revocable director sessions."""
import hashlib
import hmac
import secrets
import time
from http.cookies import SimpleCookie
from accounting import transaction

COOKIE='__Host-topshinalar-director'
PRECOOKIE='__Host-topshinalar-browser'
TTL=8*3600


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def migrate(s):
    with s.db,transaction(s):
        for sql in (
            'CREATE TABLE IF NOT EXISTS director_sessions(token_hash TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),expires INTEGER NOT NULL)',
            'CREATE TABLE IF NOT EXISTS director_logins(code_hash TEXT PRIMARY KEY,browser_hash TEXT NOT NULL UNIQUE,expires INTEGER NOT NULL,approved_by INTEGER REFERENCES users(id))',
            'CREATE TABLE IF NOT EXISTS director_replays(hash TEXT PRIMARY KEY,expires INTEGER NOT NULL)',
            'CREATE TABLE IF NOT EXISTS director_limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL)',
            "CREATE TRIGGER IF NOT EXISTS director_revoke AFTER UPDATE OF active,role ON users WHEN NEW.active=0 OR NEW.role<>'director' BEGIN DELETE FROM director_sessions WHERE uid=NEW.id; DELETE FROM director_logins WHERE approved_by=NEW.id; END",
        ):s.db.execute(sql)


def cookie(name,value,age):return f'{name}={value}; Path=/; Max-Age={age}; HttpOnly; Secure; SameSite=Strict'


def cookies(header):
    try:
        values=SimpleCookie();values.load(header or '')
        return {k:v.value for k,v in values.items()}
    except Exception:return {}


def csrf(token):return digest(token+':csrf')


def limit(s,key,maximum=10,window=300):
    stamp=int(time.time());key=digest(key)
    # Caller commits failed attempts too; do not roll back throttling on denial.
    from contextlib import nullcontext
    owner=nullcontext() if s.db.in_transaction else s.db
    with owner,transaction(s):
        s.db.execute('DELETE FROM director_limits WHERE expires<?',(stamp,))
        s.db.execute('INSERT INTO director_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,stamp+window))
        count=s.db.execute('SELECT count FROM director_limits WHERE key=?',(key,)).fetchone()[0]
    if count>maximum:raise PermissionError('rate limit')


def start(s,browser,ip):
    limit(s,'start:'+ip,5)
    code=secrets.token_hex(6).upper();stamp=int(time.time())
    with s.db,transaction(s):
        s.db.execute('DELETE FROM director_logins WHERE expires<? OR browser_hash=?',(stamp,digest(browser)))
        s.db.execute('INSERT INTO director_logins VALUES(?,?,?,NULL)',(digest(code),digest(browser),stamp+180))
    return code


def approve(s,uid,code):
    s.director(uid);limit(s,'approval:'+str(uid),10)
    with transaction(s):
        changed=s.db.execute('UPDATE director_logins SET approved_by=? WHERE code_hash=? AND expires>? AND approved_by IS NULL',(uid,digest(code.strip().upper()),int(time.time()))).rowcount
        if not changed:raise ValueError('login expired or used')
        s.log(uid,'director_login_approved',None)


def issue(s,uid):
    s.director(uid);token=secrets.token_urlsafe(32)
    s.db.execute('DELETE FROM director_sessions WHERE expires<?',(int(time.time()),))
    s.db.execute('INSERT INTO director_sessions VALUES(?,?,?)',(digest(token),uid,int(time.time())+TTL))
    s.log(uid,'director_session_created',None)
    return token


def poll(s,browser):
    with s.db,transaction(s):
        row=s.db.execute('SELECT * FROM director_logins WHERE browser_hash=? AND expires>?',(digest(browser),int(time.time()))).fetchone()
        if not row:raise PermissionError()
        if row['approved_by'] is None:return None
        token=issue(s,row['approved_by'])
        s.db.execute('DELETE FROM director_logins WHERE code_hash=?',(row['code_hash'],))
        return token


def telegram(s,raw,bot_token):
    from miniapp import authenticate
    user=authenticate(raw,bot_token,max_age=300);s.director(user['id'])
    with s.db,transaction(s):
        s.db.execute('DELETE FROM director_replays WHERE expires<?',(int(time.time()),))
        try:s.db.execute('INSERT INTO director_replays VALUES(?,?)',(digest(raw),int(time.time())+600))
        except __import__('sqlite3').IntegrityError:raise PermissionError('replay') from None
        return issue(s,user['id'])


def identity(s,header,csrf_header=None,write=False):
    token=cookies(header).get(COOKIE,'')
    if not token:raise PermissionError()
    row=s.db.execute('SELECT uid FROM director_sessions WHERE token_hash=? AND expires>?',(digest(token),int(time.time()))).fetchone()
    if not row:raise PermissionError()
    s.director(row['uid'])
    if write and not hmac.compare_digest(csrf_header or '',csrf(token)):raise PermissionError('csrf')
    return s.user(row['uid']),token
