import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from backup import create_backup
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
