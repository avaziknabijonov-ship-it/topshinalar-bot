"""Telegram-approved sign-in for the Windows desktop app.

Same model as the director cabinet login: the desktop window shows a one-use
code, the person sends it to the bot from their own Telegram account, and only
then the server issues an HttpOnly session cookie to the window that asked.
Telegram stays the only identity provider; roles and permissions are still
evaluated on every request by the existing code.  Nothing here touches the
Mini App's X-Telegram-Init-Data path or the director cabinet tables.
"""
import hashlib
import hmac
import json
import secrets
import time
from accounting import transaction
from director_auth import cookie, cookies, digest, limit

COOKIE = '__Host-topshinalar-desktop'
PRECOOKIE = '__Host-topshinalar-device'
TTL = 8 * 3600
CODE_TTL = 180
LOOPBACK = {'127.0.0.1', '::1'}


def migrate(s):
    with s.db, transaction(s):
        for sql in (
            'CREATE TABLE IF NOT EXISTS desktop_logins(code_hash TEXT PRIMARY KEY,device_hash TEXT NOT NULL UNIQUE,expires INTEGER NOT NULL,approved_by INTEGER REFERENCES users(id))',
            'CREATE TABLE IF NOT EXISTS desktop_sessions(token_hash TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),expires INTEGER NOT NULL)',
            # Same revocation rule as director sessions: suspending a person ends their sessions.
            'CREATE TRIGGER IF NOT EXISTS desktop_revoke AFTER UPDATE OF active ON users WHEN NEW.active=0 BEGIN DELETE FROM desktop_sessions WHERE uid=NEW.id; DELETE FROM desktop_logins WHERE approved_by=NEW.id; END',
        ):
            s.db.execute(sql)


def csrf(token):
    return digest(token + ':desktop-csrf')


def client_ip(handler):
    """Behind nginx every peer is 127.0.0.1; only then trust its X-Real-IP."""
    peer = handler.client_address[0]
    forwarded = (handler.headers.get('X-Real-IP') or '').strip()
    return forwarded[:64] if peer in LOOPBACK and forwarded else peer


def start(s, device, ip):
    limit(s, 'desktop-start:' + ip, 20)
    code = secrets.token_hex(6).upper()
    stamp = int(time.time())
    with s.db, transaction(s):
        s.db.execute('DELETE FROM desktop_logins WHERE expires<? OR device_hash=?', (stamp, digest(device)))
        s.db.execute('INSERT INTO desktop_logins VALUES(?,?,?,NULL)', (digest(code), digest(device), stamp + CODE_TTL))
    return code


def approve(s, uid, code):
    """Called by the bot for the Telegram account that sent the code."""
    s.user(uid)
    limit(s, 'desktop-approval:' + str(uid), 10)
    with transaction(s):
        changed = s.db.execute(
            'UPDATE desktop_logins SET approved_by=? WHERE code_hash=? AND expires>? AND approved_by IS NULL',
            (uid, digest(code.strip().upper()), int(time.time()))).rowcount
        if not changed:
            raise ValueError('login expired or used')
        s.log(uid, 'desktop_login_approved', None)


def issue(s, uid):
    s.user(uid)
    token = secrets.token_urlsafe(32)
    s.db.execute('DELETE FROM desktop_sessions WHERE expires<?', (int(time.time()),))
    s.db.execute('INSERT INTO desktop_sessions VALUES(?,?,?)', (digest(token), uid, int(time.time()) + TTL))
    s.log(uid, 'desktop_session_created', None)
    return token


def poll(s, device):
    """Returns None while waiting, otherwise (session token, user id)."""
    with s.db, transaction(s):
        row = s.db.execute('SELECT * FROM desktop_logins WHERE device_hash=? AND expires>?', (digest(device), int(time.time()))).fetchone()
        if not row:
            raise PermissionError()
        if row['approved_by'] is None:
            return None
        token = issue(s, row['approved_by'])
        s.db.execute('DELETE FROM desktop_logins WHERE code_hash=?', (row['code_hash'],))
        return token, row['approved_by']


def identity(s, header, csrf_header=None, write=False):
    token = cookies(header).get(COOKIE, '')
    if not token:
        raise PermissionError()
    row = s.db.execute('SELECT uid FROM desktop_sessions WHERE token_hash=? AND expires>?', (digest(token), int(time.time()))).fetchone()
    if not row:
        raise PermissionError()
    user = s.user(row['uid'])
    if write and not hmac.compare_digest(csrf_header or '', csrf(token)):
        raise PermissionError('csrf')
    return user, token


def handle_http(handler, path, write):
    """Dedicated /desktop-auth/* routes; auth state changes are POST-only and origin-bound."""
    from core import Store
    from staff import effective_role
    from ui_text import language, text
    s = None
    user = None
    ui_lang = language(handler.headers.get('X-UI-Language'))
    try:
        s = Store(handler.server.db_path)
        body = {}
        if write:
            if not handler.server.origin or handler.headers.get('Origin') != handler.server.origin:
                raise PermissionError('origin')
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 <= length <= 4096:
                raise ValueError('payload')
            if length:
                body = json.loads(handler.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('payload')
        values = cookies(handler.headers.get('Cookie'))
        if path == '/desktop-auth/start' and write:
            device = secrets.token_urlsafe(32)
            code = start(s, device, client_ip(handler))
            handler.extra_cookies = [cookie(PRECOOKIE, device, CODE_TTL)]
            handler.send(200, {'command': '/desktop_login ' + code, 'code': code, 'expires_in': CODE_TTL})
            return
        if path == '/desktop-auth/poll' and write:
            device = values.get(PRECOOKIE, '')
            if not device:
                raise PermissionError()
            limit(s, 'desktop-poll:' + digest(device), 100)
            result = poll(s, device)
            if result:
                token, uid = result
                handler.extra_cookies = [cookie(COOKIE, token, TTL), cookie(PRECOOKIE, '', 0)]
                if s.user(uid)['role'] == 'director':
                    # A director may also open the cabinet inside the desktop window without a second code.
                    import director_auth
                    handler.extra_cookies.append(cookie(director_auth.COOKIE, director_auth.issue(s, uid), director_auth.TTL))
                s.db.commit()
            handler.send(200, {'approved': bool(result)})
            return
        user, token = identity(s, handler.headers.get('Cookie'), handler.headers.get('X-CSRF-Token'), write)
        ui_lang = language(handler.headers.get('X-UI-Language'), user['lang'])
        if path == '/desktop-auth/me' and not write:
            handler.send(200, {'id': user['id'], 'name': user['name'], 'lang': user['lang'], 'role': effective_role(s, user['id']), 'csrf': csrf(token)})
            return
        if path == '/desktop-auth/logout' and write:
            with s.db:
                s.db.execute('DELETE FROM desktop_sessions WHERE token_hash=?', (digest(token),))
                director_token = values.get('__Host-topshinalar-director')
                if director_token:
                    s.db.execute('DELETE FROM director_sessions WHERE token_hash=? AND uid=?', (digest(director_token), user['id']))
                s.log(user['id'], 'desktop_logout', None)
            handler.extra_cookies = [cookie(COOKIE, '', 0), cookie('__Host-topshinalar-director', '', 0)]
            handler.send(200, {'ok': True})
            return
        handler.send(404, {'error': text('not_found', ui_lang)})
    except (PermissionError, ValueError, TypeError, KeyError):
        lang = language(handler.headers.get('X-UI-Language'), user['lang'] if user else 'uz')
        handler.send(403, {'error': text('permission_error', lang)})
    except Exception:
        import logging
        logging.exception('Desktop auth request failed: %s', path)
        handler.send(503, {'error': text('not_available', ui_lang)})
    finally:
        if s:
            s.db.close()
