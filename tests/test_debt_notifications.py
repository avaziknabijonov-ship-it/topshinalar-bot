"""Only a single explicitly configured fixture chat; Telegram sends are mocked."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Store
from miniapp import MiniService,initialize
from debt_notifications import migrate,enqueue

class Recorder:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def call(self,method,payload):
  self.calls.append((method,payload))
  if self.fail:raise OSError('offline')
  return {'ok':True}

class DebtNotificationTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'DIRECTOR_DEBT_CHAT_ID':'10'});self.env.start()
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';self.s=Store(self.path);self.s.configure([10,11],[20,21]);initialize(self.path);self.service=MiniService(self.s,'fixture');self.bot=self.service.b
  with self.s.db:
   self.s.db.execute("UPDATE users SET lang='ru',name='Director RU' WHERE id=11");self.s.db.execute("UPDATE users SET name='Seller A' WHERE id=20");self.s.db.execute("UPDATE users SET name='Collector B' WHERE id=21")
   self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Tyre','125');self.s.move(20,self.product,self.point,10,'in','Fixture');self.client=self.s.client(20,'Customer','+998901234567','','');self.sale=self.s.order(20,self.client,[dict(product=self.product,qty=2,price='125')],point=self.point,paid='50',payment='card')
 def tearDown(self):self.s.db.close();self.temp.cleanup();self.env.stop()
 def collect(self,key='notice-receipt-0001',**updates):
  data=dict(sale=self.sale,amount='50.25',payment='cash',expected_paid='5000');data.update(updates);return self.service.write(20,key,'collect_debt',data)['id']
 def notifications(self):return self.s.rows('SELECT n.*,o.chat,o.payload,o.sent FROM debt_payment_notifications n LEFT JOIN outbox o ON o.id=n.outbox_id ORDER BY n.payment')
 def test_partial_exact_message_only_configured_director_not_every_active_director(self):
  self.assertEqual(self.notifications(),[]);self.collect();rows=self.notifications();self.assertEqual([r['chat'] for r in rows],[10]);text=json.loads(rows[0]['payload'])['text']
  for part in ('Mijoz: Customer','To‘landi: 50.25 USD','To‘lovdan keyingi qarz: 149.75 USD','Kim tomonidan: Seller A','Usul: Naqd','Sana:'):self.assertIn(part,text)
  self.assertIn('qarzidan to‘lov',text);self.assertEqual(set(json.loads(rows[0]['payload'])),{'text'});self.assertNotIn('token',text)
 def test_full_title_amount_and_configured_directors_own_language(self):
  with patch.dict(os.environ,{'DIRECTOR_DEBT_CHAT_ID':'11'}):self.collect(amount='200')
  rows=self.notifications();self.assertEqual([r['chat'] for r in rows],[11]);text=json.loads(rows[0]['payload'])['text'];self.assertIn('Клиент погасил долг',text);self.assertIn('Оплачено: 200.00 USD',text);self.assertIn('после оплаты: 0.00 USD',text);self.assertIn('Кто принял: Seller A',text)
 def test_actual_cross_collector_not_invoice_seller_original_currency(self):
  with self.s.db:
   self.s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(self.sale,));self.s.payment(21,self.sale,'10','bank transfer')
  text=json.loads(self.notifications()[0]['payload'])['text'];self.assertIn('Kim tomonidan: Collector B',text);self.assertIn('10.00 UZS',text);self.assertNotIn('USD',text);self.assertIn('Usul: Bank',text)
 def test_replay_repeat_enqueue_and_cleanup_do_not_duplicate_or_reroute(self):
  first=self.collect();self.assertEqual(self.collect(),first)
  with self.s.db:enqueue(self.s,first['payment'])
  self.assertEqual(len(self.notifications()),1);api=Recorder();self.bot.drain(api);self.assertEqual(len(api.calls),1)
  with self.s.db:self.s.db.execute('DELETE FROM outbox WHERE sent=1')
  with patch.dict(os.environ,{'DIRECTOR_DEBT_CHAT_ID':'11'}):
   with self.s.db:enqueue(self.s,first['payment'])
  self.assertEqual(self.s.rows('SELECT * FROM outbox'),[]);self.assertIsNone(self.notifications()[0]['outbox_id']);self.assertEqual(self.notifications()[0]['state'],'sent');self.assertEqual(self.s.rows('PRAGMA foreign_key_check'),[])
 def test_initial_sale_invalid_and_stale_confirmation_never_create_extra_notices(self):
  self.assertEqual(self.notifications(),[])
  with self.assertRaises(ValueError):self.collect(amount='201')
  self.assertEqual(self.notifications(),[]);self.collect()
  with self.assertRaisesRegex(ValueError,'debt_changed'):self.collect(key='notice-stale-000001')
  self.assertEqual(len(self.notifications()),1)
 def test_missing_invalid_employee_or_multiple_destinations_no_fallback_business_continues(self):
  for value in ('','10,11','-10','20','99999999','9007199254740993'):
   with patch.dict(os.environ,{'DIRECTOR_DEBT_CHAT_ID':value}):
    with self.s.db:self.s.payment(20,self.sale,'1','cash')
  self.assertEqual(self.notifications(),[]);self.assertEqual(self.s.one('sales',self.sale)['paid'],5600)
 def test_revocation_at_delivery_does_not_fall_back_to_other_director(self):
  self.collect()
  with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=10')
  api=Recorder();self.bot.drain(api);self.assertEqual(api.calls,[]);self.assertEqual(self.notifications()[0]['state'],'skipped')
  with self.s.db:self.s.db.execute("UPDATE users SET active=1 WHERE id=10")
  self.collect(key='notice-second-0001',amount='10',expected_paid='10025')
  with self.s.db:self.s.db.execute("UPDATE users SET role='employee' WHERE id=10")
  self.bot.drain(api);self.assertEqual(api.calls,[]);self.assertTrue(all(r['state']=='skipped' and r['sent']==1 for r in self.notifications()))
 def test_destination_change_cancels_old_pending_without_forwarding(self):
  self.collect();api=Recorder()
  with patch.dict(os.environ,{'DIRECTOR_DEBT_CHAT_ID':'11'}):self.bot.drain(api)
  self.assertEqual(api.calls,[]);self.assertEqual(self.notifications()[0]['state'],'skipped')
 def test_offline_delivery_does_not_undo_payment_recovers_once(self):
  self.collect();api=Recorder(fail=True);self.bot.drain(api);self.assertEqual(self.notifications()[0]['state'],'queued');self.assertEqual(self.notifications()[0]['sent'],0);self.assertEqual(self.s.one('sales',self.sale)['paid'],10025)
  api=Recorder();self.bot.drain(api);self.assertEqual(len(api.calls),1);self.assertEqual(self.notifications()[0]['state'],'sent');self.bot.drain(api);self.assertEqual(len(api.calls),1)
 def test_no_send_before_commit_and_outer_rollback_discards_notice(self):
  api=Recorder()
  with self.assertRaises(RuntimeError):
   with self.s.db:
    self.s.payment(20,self.sale,'10','cash');self.bot.drain(api);self.assertEqual(api.calls,[]);raise RuntimeError('outer fail')
  self.assertEqual(self.notifications(),[]);self.assertEqual(self.s.one('sales',self.sale)['paid'],5000)
 def test_local_queue_or_marker_failure_rolls_back_payment_audit_and_outbox(self):
  add=self.s.add
  def fail(table,**fields):
   if table=='outbox':raise RuntimeError('queue failure')
   return add(table,**fields)
  with patch.object(self.s,'add',side_effect=fail):
   with self.assertRaises(RuntimeError):self.collect()
  self.assertEqual(self.notifications(),[]);self.assertEqual(self.s.one('sales',self.sale)['paid'],5000)
  with self.s.db:self.s.db.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON debt_payment_notifications BEGIN SELECT RAISE(ABORT,'notice failure'); END")
  with self.assertRaises(sqlite3.IntegrityError):self.collect()
  self.assertEqual(self.s.rows('SELECT * FROM outbox'),[]);self.assertEqual(self.s.one('sales',self.sale)['paid'],5000);self.assertEqual(len(self.s.rows('SELECT * FROM payments')),1);self.assertEqual(self.s.rows("SELECT * FROM audit WHERE action='payment'"),[])
 def test_migration_rerunnable_preserves_old_records_and_queue_no_backfill(self):
  with self.s.db:self.bot.queue(20,'Existing employee message');self.s.db.execute('DROP TABLE debt_payment_notifications')
  tables=('users','clients','products','sales','sale_items','payments','audit','outbox');before={t:self.s.rows('SELECT * FROM '+t+' ORDER BY rowid') for t in tables};migrate(self.s);migrate(self.s)
  self.assertEqual({t:self.s.rows('SELECT * FROM '+t+' ORDER BY rowid') for t in tables},before);self.assertEqual(self.notifications(),[])
  self.s.db.close();self.s=Store(self.path);self.assertEqual({t:self.s.rows('SELECT * FROM '+t+' ORDER BY rowid') for t in tables},before);self.assertEqual(self.s.rows('PRAGMA foreign_key_check'),[])
 def test_legacy_bot_command_uses_same_single_notification_path(self):
  with self.s.db:self.bot.execute(21,'pay',dict(sale=self.sale,amount='10',payment='card'))
  self.assertEqual(len(self.notifications()),1);self.assertIn('Kim tomonidan: Collector B',json.loads(self.notifications()[0]['payload'])['text'])
