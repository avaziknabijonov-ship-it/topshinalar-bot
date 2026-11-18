"""Category notices go to a director group topic only when configured; Telegram is mocked."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bot import Bot
from core import Store, now
from miniapp import MiniService, initialize
from test_miniapp import TOKEN
import topic_notices

ENV = {'NOTIFY_PRIXOD': '-100111:5', 'NOTIFY_KASSA': '-100111:6', 'NOTIFY_OTKAZMA': '-100111:7'}


class Recorder:
    def __init__(self, members=2, kind='supergroup', fail=False):
        self.calls, self.members, self.kind, self.fail = [], members, kind, fail

    def call(self, method, payload):
        if self.fail:
            raise OSError('offline')
        self.calls.append((method, payload))
        if method == 'getChat':
            return {'type': self.kind}
        if method == 'getChatMemberCount':
            return self.members
        return {'ok': True}

    def sent(self):
        return [p for m, p in self.calls if m == 'sendMessage']


class TopicNoticeTests(unittest.TestCase):
    def setUp(self):
        topic_notices._checked.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'db'
        self.s = Store(self.path)
        self.s.configure([10], [20])
        initialize(self.path)
        self.api = MiniService(self.s, TOKEN)
        self.bot = Bot(self.s)
        with self.s.db:
            for person in (10, 20):
                self.s.set_contact_phone(person, '+9989055500' + str(person))
            self.point = self.s.add('points', name='Sklad')
            self.product = self.s.product(10, 'Tyre 315/80', '20')
            self.client = self.s.client(20, 'Customer', '+998901234567', '', '')
            self.supplier = self.s.supplier_save(10, 'Alpha', '+998901234567', '')
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        topic_notices.poll(self.s)  # first run only sets the cursor

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()
        self.env.stop()

    def receive(self):
        with self.s.db:
            self.s.receive(20, self.product, self.supplier, '10.00', [{'point': self.point, 'qty': 5}], 'Inv', now()[:10], 'USD')

    def sell(self, paid='20', key='topic-notice-sale-0001'):
        return self.api.write(20, key, 'sell', {'client': self.client, 'point': self.point, 'items': [{'product': self.product, 'qty': 1, 'price': '20', 'point': self.point}], 'paid': paid, 'payment': 'naqd'})['id']

    def routed(self):
        return [(r['chat'], json.loads(r['payload'])) for r in self.s.rows("SELECT * FROM outbox WHERE payload LIKE '%\"route\"%' ORDER BY id")]

    def test_nothing_is_back_filled_on_first_run(self):
        self.receive()
        self.sell()
        with patch.dict(os.environ, {'NOTIFY_PRIXOD': '', 'NOTIFY_KASSA': '', 'NOTIFY_OTKAZMA': ''}):
            self.assertEqual(topic_notices.poll(self.s), 0)
        self.assertEqual(self.routed(), [])

    def test_unconfigured_sends_nothing_and_does_not_flood_later(self):
        with patch.dict(os.environ, {'NOTIFY_PRIXOD': '', 'NOTIFY_KASSA': '', 'NOTIFY_OTKAZMA': ''}):
            self.receive()
            topic_notices.poll(self.s)
        self.assertEqual(self.routed(), [])
        topic_notices.poll(self.s)  # enabled now, but old events stay old
        self.assertEqual(self.routed(), [])

    def test_prixod_and_sale_go_to_their_own_topics(self):
        self.receive()
        sale = self.sell()
        topic_notices.poll(self.s)
        rows = self.routed()
        self.assertEqual([(c, p['route'], p['message_thread_id']) for c, p in rows], [(-100111, 'prixod', 5), (-100111, 'kassa', 6)])
        self.assertIn('Prixod', rows[0][1]['text'])
        self.assertIn('Alpha', rows[0][1]['text'])
        self.assertIn(f'#{sale}', rows[1][1]['text'])
        self.assertIn('20.00 USD', rows[1][1]['text'])

    def test_sale_fully_on_credit_is_not_a_cash_receipt(self):
        self.receive()
        topic_notices.poll(self.s)
        before = len(self.routed())
        self.sell(paid='0')
        topic_notices.poll(self.s)
        self.assertEqual(len(self.routed()), before)

    def test_debt_payment_goes_to_kassa(self):
        self.receive()
        sale = self.sell(paid='5')
        topic_notices.poll(self.s)
        with self.s.db:
            self.s.payment(20, sale, '10', 'naqd')
        topic_notices.poll(self.s)
        last = self.routed()[-1][1]
        self.assertEqual(last['route'], 'kassa')
        self.assertIn('10.00 USD', last['text'])
        self.assertIn('5.00 USD', last['text'])  # remaining debt

    def test_manager_money_goes_to_otkazma_and_expense_to_kassa(self):
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
            self.s.manager_record(20, 20, 'expense', '5', 'Benzin', now()[:10], 'USD')
        topic_notices.poll(self.s)
        got = [(p['route'], p['message_thread_id']) for _, p in self.routed()]
        self.assertEqual(got, [('otkazma', 7), ('kassa', 6)])

    def test_destination_without_topic_has_no_thread_id(self):
        with patch.dict(os.environ, {'NOTIFY_KASSA': '-100222'}):
            self.receive()
            self.sell()
            topic_notices.poll(self.s)
        kassa = [p for _, p in self.routed() if p['route'] == 'kassa'][0]
        self.assertNotIn('message_thread_id', kassa)

    def test_invalid_destinations_are_ignored(self):
        for bad in ('12345', '@channel', '-1', '-100111:0', '-100111:abc', '-100111:5:6'):
            with patch.dict(os.environ, {'NOTIFY_KASSA': bad}):
                self.assertIsNone(topic_notices.destination('kassa'), bad)

    def test_delivery_sends_to_group_topic_and_strips_marker(self):
        self.receive()
        topic_notices.poll(self.s)
        rec = Recorder()
        self.bot.drain(rec)
        sent = rec.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual((sent[0]['chat_id'], sent[0]['message_thread_id']), (-100111, 5))
        self.assertNotIn('route', sent[0])
        self.assertEqual(self.s.rows('SELECT * FROM outbox WHERE sent=0'), [])

    def test_group_with_a_stranger_is_never_written_to(self):
        self.receive()
        topic_notices.poll(self.s)
        rec = Recorder(members=3)  # bot + 1 director + 1 stranger
        self.bot.drain(rec)
        self.assertEqual(rec.sent(), [])
        self.assertEqual(self.s.rows('SELECT * FROM outbox WHERE sent=0'), [])

    def test_non_group_chat_is_never_written_to(self):
        self.receive()
        topic_notices.poll(self.s)
        rec = Recorder(kind='private')
        self.bot.drain(rec)
        self.assertEqual(rec.sent(), [])

    def test_telegram_outage_keeps_the_notice_for_retry(self):
        self.receive()
        topic_notices.poll(self.s)
        self.bot.drain(Recorder(fail=True))
        self.assertEqual(len(self.s.rows('SELECT * FROM outbox WHERE sent=0')), 1)
        rec = Recorder()
        self.bot.drain(rec)
        self.assertEqual(len(rec.sent()), 1)

    def test_changed_destination_drops_queued_notice(self):
        self.receive()
        topic_notices.poll(self.s)
        rec = Recorder()
        with patch.dict(os.environ, {'NOTIFY_PRIXOD': '-100999:5'}):
            self.bot.drain(rec)
        self.assertEqual(rec.sent(), [])

    def test_cursor_prevents_duplicates(self):
        self.receive()
        topic_notices.poll(self.s)
        topic_notices.poll(self.s)
        self.assertEqual(len(self.routed()), 1)

    def test_russian_text_when_requested(self):
        with patch.dict(os.environ, {'NOTIFY_LANG': 'ru'}):
            self.receive()
            topic_notices.poll(self.s)
        self.assertIn('Приход', self.routed()[0][1]['text'])


if __name__ == '__main__':
    unittest.main()
