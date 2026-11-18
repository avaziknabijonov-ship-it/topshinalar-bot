from pathlib import Path
import json
import re
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from core import Store
from miniapp import MiniServer, initialize
from test_miniapp import TOKEN, signed

ROOT = Path(__file__).resolve().parents[1]


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 't.sqlite3'
        s = Store(self.path)
        s.configure([10], [20])
        s.db.close()
        initialize(self.path)
        self.server = MiniServer(('127.0.0.1', 0), self.path, TOKEN, 'https://cabinet.test')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def get(self, path, headers=None):
        try:
            with urlopen(Request(self.base + path, headers=headers or {})) as r:
                return r.status, r.headers, r.read()
        except HTTPError as e:
            return e.code, e.headers, e.read()

    def test_security_headers_on_pages_and_api_errors(self):
        for path in ('/', '/api/me', '/healthz'):
            _, h, _ = self.get(path)
            self.assertIn("form-action 'self'", h['Content-Security-Policy'])
            self.assertIn("frame-ancestors https://web.telegram.org", h['Content-Security-Policy'])
            self.assertIn("object-src 'none'", h['Content-Security-Policy'])
            self.assertEqual(h['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(h['Referrer-Policy'], 'no-referrer')
            self.assertEqual(h['Cross-Origin-Resource-Policy'], 'same-origin')
            self.assertIn('geolocation=()', h['Permissions-Policy'])
            self.assertEqual(h['Cache-Control'], 'no-store')

    def test_healthz_is_public_minimal_and_checks_the_database(self):
        code, _, body = self.get('/healthz')
        self.assertEqual((code, json.loads(body)), (200, {'ok': True}))
        self.server.db_path = str(Path(self.temp.name) / 'missing' / 'x.sqlite3')
        code, _, body = self.get('/healthz')
        self.assertEqual((code, json.loads(body)), (503, {'ok': False}))

    def test_denied_requests_are_logged_without_secrets(self):
        with self.assertLogs(level='WARNING') as captured:
            code, _, _ = self.get('/api/me', {'X-Telegram-Init-Data': 'hash=SECRET-INIT-DATA', 'X-Real-IP': '203.0.113.7'})
        self.assertEqual(code, 403)
        line = '\n'.join(captured.output)
        self.assertIn('request denied', line)
        self.assertIn('ip=203.0.113.7', line)
        self.assertIn('path=/api/me', line)
        self.assertNotIn('SECRET-INIT-DATA', line)
        self.assertNotIn(TOKEN, line)

    def test_forged_real_ip_values_are_not_logged_verbatim(self):
        with self.assertLogs(level='WARNING') as captured:
            self.get('/api/me', {'X-Real-IP': '1.2.3.4 ip=9.9.9.9 FAKE LOG LINE'})
        text = '\n'.join(captured.output)
        self.assertNotIn('FAKE LOG LINE', text)
        self.assertIn('ip=127.0.0.1', text)

    def test_valid_signed_request_is_not_logged_as_denied(self):
        with self.assertNoLogs(level='WARNING'):
            code, _, _ = self.get('/api/me', {'X-Telegram-Init-Data': signed(20)})
        self.assertEqual(code, 200)

    def test_filter_matches_the_apps_real_log_line_and_extracts_the_address(self):
        conf = (ROOT / 'deploy' / 'fail2ban' / 'topshinalar-miniapp.conf').read_text()
        pattern = re.search(r'(?m)^failregex\s*=\s*(.+)$', conf).group(1).replace('<ADDR>', r'(?P<ip>[0-9A-Fa-f:.]+)')
        with self.assertLogs(level='WARNING') as captured:
            self.get('/api/me', {'X-Real-IP': '203.0.113.7'})
        line = captured.records[0].getMessage()
        match = re.search(pattern, line)
        self.assertIsNotNone(match, line)
        self.assertEqual(match.group('ip'), '203.0.113.7')
        # A signed-in user's normal traffic never matches.
        self.assertIsNone(re.search(pattern, 'GET /api/me 200 ip=203.0.113.7'))


class DeploymentHardeningTests(unittest.TestCase):
    UNITS = ('topshinalar', 'topshinalar-miniapp', 'topshinalar-backup', 'topshinalar-catalog-sync')
    REQUIRED = ('NoNewPrivileges=true', 'CapabilityBoundingSet=', 'RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX', 'PrivateTmp=true',
                'ProtectKernelTunables=true', 'LockPersonality=true', 'RestrictSUIDSGID=true', 'SystemCallArchitectures=native')

    def test_every_service_unit_keeps_the_hardening_set(self):
        for name in self.UNITS:
            text = (ROOT / 'deploy' / (name + '.service')).read_text()
            for line in self.REQUIRED:
                self.assertRegex(text, r'(?m)^' + re.escape(line) + '$', (name, line))

    def test_units_and_configs_contain_no_secrets(self):
        for file in [f for f in (ROOT / 'deploy').rglob('*') if f.is_file()] + [ROOT / 'compose.yaml', ROOT / '.env.example']:
            text = file.read_text(errors='ignore')
            self.assertIsNone(re.search(r'\b\d{8,}:[A-Za-z0-9_-]{30,}\b', text), file)
            self.assertNotRegex(text, r'(?i)BOT_TOKEN=\S+', file)

    def test_nginx_template_limits_and_hides_the_server(self):
        text = (ROOT / 'deploy' / 'miniapp.nginx.conf').read_text()
        for needle in ('server_tokens off', 'limit_req_zone', 'client_body_timeout', 'X-Content-Type-Options', 'topshinalar_login', 'client_max_body_size 6m'):
            self.assertIn(needle, text)
        self.assertEqual(text.count('{'), text.count('}'))
        proxy = (ROOT / 'deploy' / 'topshinalar-proxy.inc').read_text()
        self.assertIn('proxy_set_header X-Real-IP $remote_addr;', proxy)
        self.assertIn('http://127.0.0.1:8080', proxy)

    def test_compose_publishes_only_loopback_and_has_healthcheck(self):
        text = (ROOT / 'compose.yaml').read_text()
        self.assertIn('"127.0.0.1:8080:8080"', text)
        self.assertIn('/healthz', text)


class BackupRetentionTests(unittest.TestCase):
    def names(self, directory):
        return sorted(f.name for f in Path(directory).iterdir())

    def fixture(self, directory, count):
        made = []
        for i in range(count):
            name = f'topshinalar-2026010{i + 1}T000000Z-{i:08x}.sqlite3'
            (Path(directory) / name).write_bytes(b'x')
            made.append(name)
        return made

    def test_prune_keeps_newest_and_never_touches_foreign_files(self):
        import backup
        with tempfile.TemporaryDirectory() as d:
            made = self.fixture(d, 5)
            (Path(d) / 'notes.txt').write_text('mine')
            (Path(d) / 'topshinalar-manual-copy.sqlite3').write_bytes(b'manual')
            (Path(d) / 'restore-check-abc').mkdir()
            removed = backup.prune_backups(d, 2)
            self.assertEqual(removed, made[:3])
            self.assertEqual(self.names(d), sorted(made[3:] + ['notes.txt', 'topshinalar-manual-copy.sqlite3', 'restore-check-abc']))

    def test_prune_with_fewer_files_than_keep_deletes_nothing_and_rejects_bad_keep(self):
        import backup
        with tempfile.TemporaryDirectory() as d:
            made = self.fixture(d, 2)
            self.assertEqual(backup.prune_backups(d, 5), [])
            for bad in (0, -1, None, True, 1.5):
                with self.assertRaises(ValueError):
                    backup.prune_backups(d, bad)
            self.assertEqual(self.names(d), sorted(made))

    def test_prune_does_not_follow_symlinks(self):
        import backup
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'important.sqlite3'
            target.write_bytes(b'keep me')
            self.fixture(d, 2)
            link = Path(d) / 'topshinalar-20250101T000000Z-deadbeef.sqlite3'
            link.symlink_to(target)
            backup.prune_backups(d, 1)
            self.assertTrue(target.exists())
            self.assertTrue(link.is_symlink())

    def test_cli_keeps_everything_by_default_and_prunes_only_with_keep(self):
        import subprocess, sys, sqlite3
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'live.sqlite3'
            s = Store(db); s.configure([10], []); s.db.close()
            out = Path(d) / 'backups'
            run = lambda *extra: subprocess.run([sys.executable, str(ROOT / 'backup.py'), '--source', str(db), '--directory', str(out), *extra], capture_output=True, text=True)
            for _ in range(3):
                self.assertEqual(run().returncode, 0)
            self.assertEqual(len(list(out.glob('topshinalar-*.sqlite3'))), 3)
            result = run('--keep', '2')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list(out.glob('topshinalar-*.sqlite3'))), 2)
            self.assertNotEqual(run('--keep', '0').returncode, 0)
            self.assertEqual(len(list(out.glob('topshinalar-*.sqlite3'))), 2)


if __name__ == '__main__':
    unittest.main()
