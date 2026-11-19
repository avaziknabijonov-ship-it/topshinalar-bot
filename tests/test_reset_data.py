import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

import reset_data
from core import Store


class ResetDataTests(unittest.TestCase):
    def make(self, temp):
        path = Path(temp) / 'db.sqlite3'
        s = Store(path)
        s.configure([10], [20])
        with s.db:
            point = s.add('points', name='Test ombor')
            product = s.product(10, 'Test shina 315/80 R22.5', '125')
            s.client(20, 'Test mijoz', '+998901234567', '', '')
            supplier = s.supplier_save(10, 'Test yetkazib beruvchi', '+998901111111', '')
            s.receive(20, product, supplier, '90', [{'point': point, 'qty': 5}], 'A', '2026-11-19', 'USD')
            s.db.execute("INSERT INTO meta(key,value) VALUES('topic_notice_cursor','999') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        s.db.close() if hasattr(s.db, 'close') else None
        return path

    def count(self, path, table):
        with closing(sqlite3.connect(path)) as c:
            return c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make(temp)
            before = self.count(path, 'products')
            self.assertEqual(reset_data.main(['--db', str(path), '--backup-dir', temp + '/b']), 0)
            self.assertEqual(self.count(path, 'products'), before)
            self.assertFalse((Path(temp) / 'b').exists())

    def test_confirm_wipes_business_data_keeps_staff_and_backs_up(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make(temp)
            users = self.count(path, 'users')
            self.assertGreater(self.count(path, 'products'), 0)
            self.assertEqual(reset_data.main(['--db', str(path), '--backup-dir', temp + '/b', '--confirm']), 0)
            for table in ('products', 'points', 'clients', 'stock', 'suppliers', 'receipts', 'inventory_lots', 'audit'):
                self.assertEqual(self.count(path, table), 0, table)
            self.assertEqual(self.count(path, 'users'), users)
            with closing(sqlite3.connect(path)) as c:
                self.assertIsNone(c.execute("SELECT value FROM meta WHERE key='topic_notice_cursor'").fetchone())
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(len(list((Path(temp) / 'b').glob('topshinalar-*.sqlite3'))), 1)
            # the cleaned database is fully usable again
            s = Store(path)
            with s.db:
                s.add('points', name='Yangi ombor')
                s.product(10, 'Yangi shina 12.00 R20', '210')
            self.assertEqual(self.count(path, 'products'), 1)


if __name__ == '__main__':
    unittest.main()
