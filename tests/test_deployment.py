import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from backup import create_backup, verify_restore
from core import Store


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'topshinalar.sqlite3'
        self.s=Store(str(self.source))
        self.s.configure([10],[20])
        self.directory=self.root/'backups'

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()

    def test_backup_includes_committed_wal_and_keeps_permissions(self):
        self.s.db.execute('PRAGMA wal_autocheckpoint=0')
        with self.s.db:self.s.client(20,'WAL client','+998901234567','Toshkent','')
        destination=create_backup(self.source,self.directory)
        with sqlite3.connect(destination) as conn:
            self.assertEqual(conn.execute('SELECT name FROM clients').fetchone()[0],'WAL client')
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        if os.name!='nt':self.assertEqual(destination.stat().st_mode & 0o777,0o600)

    def test_repeated_backups_preserve_earlier_snapshot(self):
        first=create_backup(self.source,self.directory)
        original=first.read_bytes()
        with self.s.db:self.s.client(20,'New client','','','')
        second=create_backup(self.source,self.directory)
        self.assertNotEqual(first,second)
        self.assertEqual(first.read_bytes(),original)
        with sqlite3.connect(second) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)

    def test_verified_restore_compares_schema_and_without_rowid_tables(self):
        with self.s.db:
            self.s.db.execute('CREATE TABLE composite_fixture(a TEXT,b INTEGER,value BLOB,PRIMARY KEY(a,b)) WITHOUT ROWID')
            self.s.db.executemany('INSERT INTO composite_fixture VALUES(?,?,?)',[('z',2,b'blob'),('a',1,b'other')])
            self.s.client(20,'Restore fixture','','','')
        before=self.source.read_bytes()
        destination=create_backup(self.source,self.directory,verify=True)
        counts=verify_restore(destination)
        self.assertEqual(counts['composite_fixture'],2)
        self.assertEqual(counts['clients'],1)
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(list(self.directory.glob('restore-check-*')),[])

    def test_failed_restore_verification_never_publishes_or_replaces_a_backup(self):
        from unittest.mock import patch
        first=create_backup(self.source,self.directory,verify=True)
        before=first.read_bytes()
        with patch('backup.verify_restore',side_effect=ValueError('restore failed')):
            with self.assertRaises(ValueError):create_backup(self.source,self.directory,verify=True)
        self.assertEqual(first.read_bytes(),before)
        self.assertEqual(list(self.directory.iterdir()),[first])

    def test_foreign_key_damage_is_rejected_before_publication(self):
        first=create_backup(self.source,self.directory)
        original=first.read_bytes()
        with sqlite3.connect(self.source) as conn:
            conn.execute("INSERT INTO clients(name,phone,address,note,owner,created) VALUES('Broken','','','',999,'2026-01-01')")
        with self.assertRaisesRegex(ValueError,'integrity'):create_backup(self.source,self.directory,verify=True)
        self.assertEqual(first.read_bytes(),original)
        self.assertEqual(list(self.directory.iterdir()),[first])

    def test_restore_detects_schema_tampering(self):
        from unittest.mock import patch
        from storage import snapshot
        destination=create_backup(self.source,self.directory)
        def altered(source,target):
            snapshot(source,target)
            with sqlite3.connect(target) as conn:conn.execute('CREATE TABLE unexpected_fixture(id INTEGER)')
        with patch('backup.snapshot',side_effect=altered):
            with self.assertRaisesRegex(ValueError,'schema'):verify_restore(destination)

    def test_missing_source_does_not_create_empty_database(self):
        missing=self.root/'missing.sqlite3'
        with self.assertRaises(sqlite3.Error):create_backup(missing,self.directory)
        self.assertFalse(missing.exists())
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_corrupt_source_does_not_replace_previous_backup(self):
        first=create_backup(self.source,self.directory)
        original=first.read_bytes()
        corrupt=self.root/'corrupt.sqlite3'
        corrupt.write_bytes(b'not a sqlite database')
        with self.assertRaises(sqlite3.Error):create_backup(corrupt,self.directory)
        self.assertEqual(first.read_bytes(),original)
        self.assertEqual(list(self.directory.iterdir()),[first])

    def test_direct_entry_point_rejects_second_process_and_releases_lock(self):
        env=dict(os.environ,DB_PATH=str(self.source))
        code="import bot,time; bot.run_bot=lambda: (print('ready',flush=True),time.sleep(30)); bot.main()"
        first=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(first.stdout.readline().strip(),'ready')
            second=subprocess.run([sys.executable,'-c',"import bot; bot.run_bot=lambda: print('entered'); bot.main()"],env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(second.returncode,0)
            self.assertNotIn('entered',second.stdout)
        finally:
            first.terminate();first.communicate(timeout=10)
        third=subprocess.run([sys.executable,'-c',"import bot; bot.run_bot=lambda: print('entered'); bot.main()"],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(third.returncode,0,third.stderr)
        self.assertIn('entered',third.stdout)
