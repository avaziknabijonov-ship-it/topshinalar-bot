"""Private-document access tests use synthetic PDFs, never company originals."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import company_documents as documents
import director_auth as auth
from core import Store
from miniapp import MiniServer, ROOT
from test_miniapp import TOKEN, signed


class CompanyDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.s = Store(self.base/'test.sqlite3')
        self.s.configure([10], [20, 21])
        self.directory = self.base/'private-documents'
        self.directory.mkdir()
        self.payload = b'%PDF-1.4\nSynthetic certificate fixture\n%%EOF\n'
        for filename in documents.ROUTES.values():
            (self.directory/filename).write_bytes(self.payload)
        self.env = patch.dict(os.environ, {'COMPANY_DOCUMENTS_DIR':str(self.directory)})
        self.env.start()
        self.server = MiniServer(('127.0.0.1', 0), self.base/'test.sqlite3', TOKEN, 'https://bot.example.uz')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.env.stop(); self.s.db.close(); self.temp.cleanup()

    def get(self, path='/company/registration.pdf', uid=None, headers=None):
        values = dict(headers or {})
        if uid is not None: values['X-Telegram-Init-Data'] = signed(uid)
        try:
            response = urlopen(Request(self.url+path, headers=values), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_anonymous_forged_expired_unknown_and_inactive_cannot_read_files(self):
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=21')
        headers = [{}, {'X-Telegram-Init-Data':'forged'},
                   {'X-Telegram-Init-Data':signed(20, age=4000)},
                   {'X-Telegram-Init-Data':signed(999)},
                   {'X-Telegram-Init-Data':signed(21)}]
        with patch('company_documents.read_document') as reader:
            for path in documents.ROUTES:
                for values in headers:
                    status, body, _ = self.get(path, headers=values)
                    self.assertEqual(status, 403)
                    self.assertNotIn(self.payload, body)
            reader.assert_not_called()

    def test_active_staff_and_director_get_attachments_with_no_cache(self):
        for path, filename in documents.ROUTES.items():
            for uid in (10, 20):
                status, body, headers = self.get(path, uid)
                self.assertEqual((status, body), (200, self.payload))
                self.assertEqual(headers['Content-Type'], 'application/pdf')
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(headers['Content-Disposition'], 'attachment; filename="'+filename+'"')

    def test_director_cookie_is_revoked_when_account_is_disabled(self):
        with self.s.db: token = auth.issue(self.s, 10)
        headers = {'Cookie':auth.COOKIE+'='+token}
        self.assertEqual(self.get(headers=headers)[0], 200)
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=10')
        self.assertEqual(self.get(headers=headers)[0], 403)

    def test_cross_origin_is_denied_and_public_contacts_contain_no_document_links(self):
        self.assertEqual(self.get(uid=20, headers={'Origin':'https://evil.example'})[0], 403)
        status, body, _ = self.get('/company')
        self.assertEqual(status, 200)
        self.assertNotIn(b'/company/registration.pdf', body)
        self.assertNotIn(b'/company/vat.pdf', body)
        self.assertNotIn(b'/assets/quotation-attachments/', body)

    def test_disabled_missing_in_repo_and_relative_storage_have_no_fallback(self):
        for directory in ('', 'relative-path', str(ROOT/'assets/quotation-attachments'), str(self.base/'missing')):
            with patch.dict(os.environ, {'COMPANY_DOCUMENTS_DIR':directory}):
                self.assertEqual(self.get(uid=20)[0], 404)
        for name in documents.ROUTES.values():
            for suffix in ('.pdf','.png'):
                self.assertFalse((ROOT/'assets/quotation-attachments'/Path(name).with_suffix(suffix)).exists())

    def test_symlink_non_pdf_and_oversized_files_are_rejected(self):
        filename = self.directory/'company-registration.pdf'
        filename.unlink(); filename.symlink_to(self.directory/'vat-registration.pdf')
        self.assertEqual(self.get(uid=20)[0], 404)
        filename.unlink(); filename.write_bytes(b'private text, not a PDF')
        self.assertEqual(self.get(uid=20)[0], 404)
        with filename.open('wb') as stream:stream.truncate(documents.MAX_BYTES+1)
        self.assertEqual(self.get(uid=20)[0], 404)

    def test_paths_and_file_query_cannot_select_other_private_files(self):
        (self.base/'secret.pdf').write_bytes(b'%PDF-other-private-file')
        self.assertEqual(self.get('/company/../secret.pdf', 20)[0], 404)
        self.assertEqual(self.get('/assets/quotation-attachments/company-registration.pdf', 20)[0], 404)
        self.assertEqual(self.get('/company/registration.pdf?file=../secret.pdf', 20)[1], self.payload)
