import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import Store
from storage import inspect_db,discover_databases,resolve_database,migrate_database,active_ids,SingleInstance

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'Downloads'/'topshinalar-new'
        self.root.mkdir(parents=True)
        self.old=self.base/'Downloads'/'topshinalar-old'/'data'/'topshinalar.sqlite3'
        self.old.parent.mkdir(parents=True)
        self.create(self.old,15)
        self.stable=self.base/'stable'
    def tearDown(self):self.temp.cleanup()
    def create(self,path,qty):
        path.parent.mkdir(parents=True,exist_ok=True)
        s=Store(path);s.configure([10,11],[20,21])
        with s.db:
            point=s.add('points',name='Asosiy ombor')
            product=s.product(10,'Linglong 315/80 R22.5','3500000')
            s.move(20,product,point,qty,'in','start')
            s.client(20,'Mijoz','+998901234567','Toshkent','')
        s.db.close()
    def resolve(self,**kwargs):
        return resolve_database(self.root,123,base=self.stable,roots=[self.base/'Downloads'],emit=lambda s:None,**kwargs)
    def test_discover_and_migrate_readonly_keeps_original(self):
        original=self.old.read_bytes()
        result=discover_databases(self.root,123,roots=[self.base/'Downloads'])
        self.assertEqual(result,[self.old.resolve()])
        path,moved=self.resolve(ask=lambda _: '1')
        self.assertTrue(moved);self.assertEqual(inspect_db(path)['stock'],15)
        self.assertEqual(original,self.old.read_bytes())
        self.assertEqual(len(list((path.parent/'backups').glob('*.sqlite3'))),1)
        self.assertEqual(active_ids(path),{'director':'10,11','employee':'20,21'})
    def test_new_code_folder_reuses_same_stable_database(self):
        path,_=self.resolve(ask=lambda _: '1')
        other=self.base/'new-extraction';other.mkdir()
        next_path,moved=resolve_database(other,123,base=self.stable,ask=lambda _:self.fail('should not prompt'))
        self.assertEqual(path,next_path);self.assertFalse(moved)
        self.assertEqual(inspect_db(next_path)['stock'],15)
    def test_choice_lists_counts_and_does_not_merge(self):
        second=self.root/'data'/'topshinalar.sqlite3';self.create(second,3)
        messages=[]
        candidates=discover_databases(self.root,123,roots=[self.base/'Downloads'])
        choice=str(candidates.index(self.old.resolve())+1)
        path,moved=resolve_database(self.root,123,base=self.stable,roots=[self.base/'Downloads'],ask=lambda _:choice,emit=messages.append)
        self.assertEqual(inspect_db(path)['stock'],15)
        self.assertTrue(any('15 dona' in m for m in messages))
        self.assertEqual(inspect_db(second)['stock'],3)
    def test_cancel_does_not_create_database(self):
        with self.assertRaises(SystemExit):self.resolve(ask=lambda _: 'q')
        self.assertFalse((self.stable/'123'/'topshinalar.sqlite3').exists())
        self.assertEqual(inspect_db(self.old)['stock'],15)
    def test_existing_target_backed_up_before_explicit_restore(self):
        target=self.stable/'123'/'topshinalar.sqlite3';self.create(target,2)
        path,moved=self.resolve(ask=lambda _: '1',recover=True)
        self.assertTrue(moved);self.assertEqual(inspect_db(path)['stock'],15)
        backups=list((path.parent/'backups').glob('before-restore-*.sqlite3'))
        self.assertEqual(len(backups),1);self.assertEqual(inspect_db(backups[0])['stock'],2)
    def test_corrupt_target_not_silently_replaced(self):
        target=self.stable/'123'/'topshinalar.sqlite3';target.parent.mkdir(parents=True);target.write_bytes(b'broken')
        with self.assertRaises(ValueError):self.resolve(ask=lambda _: '1')
        self.assertEqual(target.read_bytes(),b'broken')
    def test_other_bot_filtered_out(self):
        (self.old.parent.parent/'.env').write_text('BOT_TOKEN=999:not-a-real-token\n')
        found=discover_databases(self.root,123,roots=[self.base/'Downloads'])
        self.assertEqual(found,[])
    def test_invalid_source_never_overwrites_target(self):
        target=self.stable/'123'/'topshinalar.sqlite3';self.create(target,2)
        bad=self.base/'bad.sqlite3';bad.write_bytes(b'bad')
        with self.assertRaises(ValueError):migrate_database(bad,target)
        self.assertEqual(inspect_db(target)['stock'],2)
    def test_wal_snapshot_includes_committed_rows(self):
        s=Store(self.old)
        with s.db:s.db.execute('UPDATE stock SET qty=18')
        target=self.stable/'123'/'topshinalar.sqlite3'
        migrate_database(self.old,target)
        self.assertEqual(inspect_db(target)['stock'],18)
        s.db.close()
    def test_instance_lock_released_after_exit(self):
        path=self.stable/'startup.lock'
        with SingleInstance(path):
            with self.assertRaises(SystemExit):
                with SingleInstance(path):pass
        with SingleInstance(path):pass
    def test_settings_roundtrip_and_recovery_from_new_folder(self):
        from start_local import save_config,load_config,saved_config
        settings=self.stable/'123'/'settings.env'
        data={'BOT_TOKEN':'123:not-a-real-token','DIRECTOR_IDS':'10','DB_PATH':str(self.old)}
        save_config(settings,data)
        self.assertEqual(load_config(settings),data)
        with patch('start_local.data_home',return_value=self.stable):self.assertEqual(saved_config(),data)
        self.assertEqual(list(settings.parent.glob('.settings-*')),[])

    def test_manual_database_path_outside_search_roots(self):
        path,moved=resolve_database(self.root,123,base=self.stable,recover=True,roots=[],ask=lambda _:str(self.old),emit=lambda _:None)
        self.assertTrue(moved)
        self.assertEqual(inspect_db(path)['stock'],15)

if __name__=='__main__':unittest.main()
