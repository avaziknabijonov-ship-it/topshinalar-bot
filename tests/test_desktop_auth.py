import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from core import Store
from bot import Bot
from miniapp import MiniServer, MiniService, initialize
from test_miniapp import TOKEN, signed
import desktop_auth as desk
import director_auth as auth

ORIGIN = 'https://desktop.test'


class DesktopAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.s = Store(self.path)
        self.s.configure([10], [20, 21])
        initialize(self.path)
        with self.s.db:
            self.point = self.s.add('points', name='Main')
            self.client = self.s.client(20, 'Customer', '+998901234567', '', '')
            self.product = self.s.product(10, 'Linglong 315/80 R22.5', '2500000')
            self.s.move(20, self.product, self.point, 10, 'in', '')

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()

    def login(self, uid):
        device = 'device-' + str(uid)
        code = desk.start(self.s, device, '10.0.0.1')
        desk.approve(self.s, uid, code)
        self.s.db.commit()
        return desk.poll(self.s, device)

    # --- core flow -------------------------------------------------------
    def test_code_flow_issues_session_for_the_approving_account_only(self):
        device = 'browser-device'
        code = desk.start(self.s, device, '10.0.0.1')
        self.assertIsNone(desk.poll(self.s, device))
        desk.approve(self.s, 20, code.lower())
        self.s.db.commit()
        token, uid = desk.poll(self.s, device)
        self.assertEqual(uid, 20)
        user, seen = desk.identity(self.s, desk.COOKIE + '=' + token)
        self.assertEqual((user['id'], seen), (20, token))
        # The code is spent and the device cookie can not mint a second session.
        with self.assertRaises(PermissionError):
            desk.poll(self.s, device)
        with self.assertRaises(ValueError):
            desk.approve(self.s, 21, code)

    def test_unknown_expired_and_foreign_devices_are_rejected(self):
        code = desk.start(self.s, 'mine', '10.0.0.1')
        with self.assertRaises(PermissionError):
            desk.poll(self.s, 'someone-else')
        with self.assertRaises(ValueError):
            desk.approve(self.s, 20, 'NOTACODE0000')
        with self.s.db:
            self.s.db.execute('UPDATE desktop_logins SET expires=?', (int(time.time()) - 1,))
        with self.assertRaises(ValueError):
            desk.approve(self.s, 20, code)
        with self.assertRaises(PermissionError):
            desk.poll(self.s, 'mine')

    def test_unknown_telegram_account_can_not_approve(self):
        code = desk.start(self.s, 'mine', '10.0.0.1')
        with self.assertRaises((PermissionError, ValueError)):
            desk.approve(self.s, 999, code)
        self.assertIsNone(desk.poll(self.s, 'mine'))

    def test_new_code_replaces_previous_code_of_the_same_device(self):
        first = desk.start(self.s, 'mine', '10.0.0.1')
        second = desk.start(self.s, 'mine', '10.0.0.1')
        with self.assertRaises(ValueError):
            desk.approve(self.s, 20, first)
        desk.approve(self.s, 20, second)

    def test_csrf_is_required_for_writes_and_not_shared_with_director_cabinet(self):
        token, _ = self.login(20)
        header = desk.COOKIE + '=' + token
        desk.identity(self.s, header, None, False)
        with self.assertRaises(PermissionError):
            desk.identity(self.s, header, None, True)
        with self.assertRaises(PermissionError):
            desk.identity(self.s, header, auth.csrf(token), True)
        desk.identity(self.s, header, desk.csrf(token), True)

    def test_suspending_a_person_revokes_sessions_and_blocks_login(self):
        token, _ = self.login(20)
        header = desk.COOKIE + '=' + token
        with self.s.db:
            self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
        with self.assertRaises(PermissionError):
            desk.identity(self.s, header)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM desktop_sessions').fetchone()[0], 0)
        with self.s.db:
            self.s.db.execute('UPDATE users SET active=1 WHERE id=20')
        with self.assertRaises(PermissionError):
            desk.identity(self.s, header)

    def test_expired_session_is_rejected(self):
        token, _ = self.login(20)
        with self.s.db:
            self.s.db.execute('UPDATE desktop_sessions SET expires=?', (int(time.time()) - 1,))
        with self.assertRaises(PermissionError):
            desk.identity(self.s, desk.COOKIE + '=' + token)

    def test_start_is_rate_limited_per_address(self):
        for _ in range(20):
            desk.start(self.s, 'a', '10.0.0.9')
        with self.assertRaises(PermissionError):
            desk.start(self.s, 'a', '10.0.0.9')
        desk.start(self.s, 'a', '10.0.0.10')

    def test_secrets_are_stored_only_as_hashes(self):
        token, _ = self.login(20)
        code = desk.start(self.s, 'raw-device', '10.0.0.1')
        stored = json.dumps([dict(r) for r in self.s.db.execute('SELECT * FROM desktop_sessions')] + [dict(r) for r in self.s.db.execute('SELECT * FROM desktop_logins')])
        for secret in (token, code, 'raw-device'):
            self.assertNotIn(secret, stored)

    # --- bot command -----------------------------------------------------
    def test_bot_command_approves_for_the_sender_and_ignores_strangers(self):
        bot = Bot(self.s)
        code = desk.start(self.s, 'mine', '10.0.0.1')
        self.s.db.commit()
        bot.process({'update_id': 1, 'message': {'from': {'id': 20, 'first_name': 'Emp'}, 'chat': {'id': 20, 'type': 'private'}, 'text': '/desktop_login ' + code}})
        token, uid = desk.poll(self.s, 'mine')
        self.assertEqual(uid, 20)
        reply = json.loads(self.s.rows('SELECT payload FROM outbox WHERE chat=20 ORDER BY id DESC LIMIT 1')[0]['payload'])['text']
        self.assertIn('Windows', reply)
        other = desk.start(self.s, 'other', '10.0.0.1')
        self.s.db.commit()
        bot.process({'update_id': 2, 'message': {'from': {'id': 999, 'first_name': 'Stranger'}, 'chat': {'id': 999, 'type': 'private'}, 'text': '/desktop_login ' + other}})
        self.assertIsNone(desk.poll(self.s, 'other'))

    # --- HTTP ------------------------------------------------------------
    def serve(self):
        server = MiniServer(('127.0.0.1', 0), self.path, TOKEN, ORIGIN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join()))
        return 'http://127.0.0.1:' + str(server.server_address[1])

    @staticmethod
    def call(base, path, body=None, cookie='', csrf='', origin=ORIGIN, extra=None):
        headers = {'Origin': origin, 'Cookie': cookie, 'X-CSRF-Token': csrf, 'Idempotency-Key': 'desktop-test-key-0001', **(extra or {})}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with urlopen(request) as r:
                return r.status, r.headers, json.loads(r.read())
        except HTTPError as e:
            return e.code, e.headers, json.loads(e.read())

    def http_login(self, base, uid):
        code, headers, data = self.call(base, '/desktop-auth/start', {})
        self.assertEqual(code, 200)
        self.assertTrue(data['command'].startswith('/desktop_login '))
        device = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.call(base, '/desktop-auth/poll', {}, device)[2], {'approved': False})
        desk.approve(self.s, uid, data['code'])
        self.s.db.commit()
        code, headers, data = self.call(base, '/desktop-auth/poll', {}, device)
        self.assertEqual((code, data), (200, {'approved': True}))
        return headers.get_all('Set-Cookie')

    def test_http_login_cookie_flags_me_logout_and_origin_binding(self):
        base = self.serve()
        self.assertEqual(self.call(base, '/desktop-auth/start', {}, origin='https://evil.test')[0], 403)
        self.assertEqual(self.call(base, '/desktop-auth/me')[0], 403)
        self.assertEqual(self.call(base, '/desktop-auth/poll', {}, desk.PRECOOKIE + '=forged')[0], 403)
        cookies = self.http_login(base, 20)
        session = next(c for c in cookies if c.startswith(desk.COOKIE + '='))
        for flag in ('HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/'):
            self.assertIn(flag, session)
        self.assertNotIn('Domain', session)
        cookie = session.split(';')[0]
        # Employees never receive a director cabinet cookie.
        self.assertFalse([c for c in cookies if c.startswith(auth.COOKIE)])
        code, _, me = self.call(base, '/desktop-auth/me', cookie=cookie)
        self.assertEqual((code, me['id'], me['role']), (200, 20, 'employee'))
        self.assertEqual(self.call(base, '/director-api/overview', cookie=cookie)[0], 403)
        self.assertEqual(self.call(base, '/desktop-auth/logout', {}, cookie)[0], 403)
        self.assertEqual(self.call(base, '/desktop-auth/logout', {}, cookie, me['csrf'], origin='https://evil.test')[0], 403)
        self.assertEqual(self.call(base, '/desktop-auth/logout', {}, cookie, me['csrf'])[0], 200)
        self.assertEqual(self.call(base, '/desktop-auth/me', cookie=cookie)[0], 403)

    def test_director_gets_cabinet_cookie_without_a_second_code(self):
        base = self.serve()
        cookies = self.http_login(base, 10)
        cabinet = next(c for c in cookies if c.startswith(auth.COOKIE + '='))
        for flag in ('HttpOnly', 'Secure', 'SameSite=Strict'):
            self.assertIn(flag, cabinet)
        header = '; '.join(c.split(';')[0] for c in cookies if not c.split(';')[0].endswith('='))
        self.assertEqual(self.call(base, '/director-api/overview', cookie=header)[0], 200)
        _, _, me = self.call(base, '/desktop-auth/me', cookie=header)
        self.assertEqual(me['role'], 'director')
        self.assertEqual(self.call(base, '/desktop-auth/logout', {}, header, me['csrf'])[0], 200)
        self.assertEqual(self.call(base, '/director-api/overview', cookie=header)[0], 403)

    def test_api_permissions_and_roles_are_the_existing_ones(self):
        base = self.serve()
        employee = next(c for c in self.http_login(base, 20) if c.startswith(desk.COOKIE)).split(';')[0]
        code, _, me = self.call(base, '/api/me', cookie=employee)
        self.assertEqual((code, me['id'], me['role']), (200, 20, 'employee'))
        self.assertIn('catalog', me['permissions'])
        # Director-only data stays closed to an employee, exactly as in the Mini App.
        self.assertEqual(self.call(base, '/api/staff', cookie=employee)[0], 403)
        # Suspending the person ends access immediately.
        with self.s.db:
            self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
        self.assertEqual(self.call(base, '/api/me', cookie=employee)[0], 403)

    def test_desktop_and_mini_app_read_and_write_the_same_database(self):
        base = self.serve()
        employee = next(c for c in self.http_login(base, 20) if c.startswith(desk.COOKIE)).split(';')[0]
        _, _, me = self.call(base, '/desktop-auth/me', cookie=employee)
        sale = {'cmd': 'sell', 'money_version': 2, 'data': {'client': self.client, 'point': self.point, 'items': [{'product': self.product, 'qty': 2, 'price': '2500000'}], 'paid': '1000000', 'payment': 'naqd'}}
        # A sale made in the Windows app ...
        code, _, _ = self.call(base, '/api/action', sale, employee, me['csrf'], extra={'Idempotency-Key': 'desktop-sale-key-0001'})
        self.assertEqual(code, 200)
        # ... is visible in the Mini App (Telegram-signed request, no cookies).
        mini = self.call(base, '/api/my-sales', extra={'X-Telegram-Init-Data': signed(20)}, origin=ORIGIN)[2]
        self.assertEqual(mini['total'], 1)
        # A sale made in the Mini App ...
        sale['data']['items'][0]['qty'] = 1
        code, _, _ = self.call(base, '/api/action', sale, extra={'X-Telegram-Init-Data': signed(20), 'Idempotency-Key': 'mini-sale-key-000001'})
        self.assertEqual(code, 200)
        # ... shows up in the Windows app, and stock is one shared number.
        desktop = self.call(base, '/api/my-sales', cookie=employee)[2]
        self.assertEqual(desktop['total'], 2)
        remaining = self.s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?', (self.product, self.point)).fetchone()[0]
        self.assertEqual(remaining, 10 - 2 - 1)
        # One row set, one database file.
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0], 2)

    def test_desktop_writes_need_session_origin_and_csrf(self):
        base = self.serve()
        employee = next(c for c in self.http_login(base, 20) if c.startswith(desk.COOKIE)).split(';')[0]
        _, _, me = self.call(base, '/desktop-auth/me', cookie=employee)
        sale = {'cmd': 'language', 'data': {'lang': 'ru'}}
        self.assertEqual(self.call(base, '/api/action', sale, employee)[0], 403)
        self.assertEqual(self.call(base, '/api/action', sale, employee, me['csrf'], origin='https://evil.test')[0], 403)
        self.assertEqual(self.call(base, '/api/action', sale, '', me['csrf'])[0], 403)
        self.assertEqual(self.call(base, '/api/action', sale, employee, me['csrf'])[0], 200)

    def test_telegram_signed_mini_app_requests_are_unchanged(self):
        base = self.serve()
        code, _, me = self.call(base, '/api/me', extra={'X-Telegram-Init-Data': signed(20)})
        self.assertEqual((code, me['id']), (200, 20))
        self.assertEqual(self.call(base, '/api/me')[0], 403)
        self.assertEqual(self.call(base, '/api/me', extra={'X-Telegram-Init-Data': signed(20, age=7200)})[0], 403)


if __name__ == '__main__':
    unittest.main()
