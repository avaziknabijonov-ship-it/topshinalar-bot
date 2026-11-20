"""Each manager gets only their own money notices, in their private chat, with their balance."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Store, now
from miniapp import initialize
import manager_dm
import manager_money


class ManagerDmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'db'
        self.s = Store(self.path)
        self.s.configure([10], [20, 30])
        initialize(self.path)
        with self.s.db:
            for person in (10, 20, 30):
                self.s.set_contact_phone(person, '+9989055500' + str(person))
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop('NOTIFY_MANAGER_DM', None)
        manager_dm.poll(self.s)  # first run only sets the cursor

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()
        self.env.stop()

    def sent(self, chat=None):
        rows = self.s.rows('SELECT * FROM outbox ORDER BY id')
        return [(r['chat'], json.loads(r['payload'])['text']) for r in rows if chat is None or r['chat'] == chat]

    def test_history_is_not_back_filled(self):
        self.s.db.execute("DELETE FROM meta WHERE key='manager_dm_cursor'")
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
        manager_dm.poll(self.s)
        self.assertEqual(self.sent(), [])

    def test_each_manager_sees_only_own_money_with_balance(self):
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
            self.s.manager_record(10, 30, 'fund', '70', 'Kassa', now()[:10], 'USD')
        manager_dm.poll(self.s)
        with self.s.db:
            self.s.manager_record(20, 20, 'expense', '5', 'Benzin', now()[:10], 'USD')
        manager_dm.poll(self.s)
        mine = self.sent(20)
        # balances are as of the poll; the bot polls every loop, so this is the post-move balance
        other = self.sent(30)
        self.assertEqual(len(mine), 2)
        self.assertEqual(len(other), 1)
        self.assertEqual(self.sent(10), [])  # director's private chat is not filled
        self.assertIn('50.00 USD', mine[0][1])
        self.assertIn('45.00 USD', mine[1][1])  # balance after the expense
        self.assertNotIn('70.00', ''.join(t for _, t in mine))
        self.assertIn('70.00 USD', other[0][1])

    def test_handover_request_and_acceptance(self):
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
        ref = manager_money.request_return(self.s, 20, {'amount': '30', 'currency': 'USD', 'note': 'Topshirdim'})
        manager_dm.poll(self.s)
        manager_money.accept_return(self.s, 10, {'entry': ref})
        manager_dm.poll(self.s)
        texts = [t for _, t in self.sent(20)]
        self.assertEqual(len(texts), 3)
        self.assertIn('30.00 USD', texts[1])
        self.assertIn('Tasdiq kutmoqda: 30.00 USD', texts[1])
        self.assertIn('qabul qilindi', texts[2])
        self.assertIn('Sizdagi qoldiq: 20.00 USD', texts[2])

    def test_can_be_turned_off(self):
        os.environ['NOTIFY_MANAGER_DM'] = '0'
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
        manager_dm.poll(self.s)
        self.assertEqual(self.sent(), [])

    def test_cursor_prevents_duplicates(self):
        with self.s.db:
            self.s.manager_record(10, 20, 'fund', '50', 'Kassa', now()[:10], 'USD')
        manager_dm.poll(self.s)
        manager_dm.poll(self.s)
        self.assertEqual(len(self.sent(20)), 1)


if __name__ == '__main__':
    unittest.main()
