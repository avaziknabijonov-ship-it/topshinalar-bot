import unittest
from unittest.mock import patch
import test_miniapp as fixtures
import test_bot as bot_fixtures
from core import normalize_contact_phone
from quotation import quotation_pdf, COMPANY_PHONE

class QuoteCreatorTests(unittest.TestCase):
    setUp=fixtures.MiniAppTests.setUp
    tearDown=fixtures.MiniAppTests.tearDown

    def quote(self,uid,key,**extra):
        return self.service.write(uid,key,'quote',{'client':self.client,'items':[{'product':self.product,'qty':1,'price':'380'}],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000',**extra})['id']

    def test_creator_is_authenticated_author_not_client_supplied_identity(self):
        with self.s.db:self.s.db.execute("UPDATE users SET name='First salesperson' WHERE id=20")
        ref=self.quote(20,'creator-first-0001',contact_phone='93 555 11 22',creator_name='Someone else',actor=21)
        quote=self.s.one('quotes',ref)
        self.assertEqual(quote['actor'],20)
        self.assertEqual(quote['creator_name'],'First salesperson')
        self.assertEqual(quote['creator_phone'],'+998935551122')
        self.assertEqual(self.s.contact_phone(20),'+998935551122')
        self.assertNotEqual(self.s.contact_phone(21),'+998935551122')

    def test_each_author_uses_their_own_saved_number_and_old_quote_is_immutable(self):
        with self.s.db:
            self.s.db.execute("UPDATE users SET name='First' WHERE id=20")
            self.s.db.execute("UPDATE users SET name='Second' WHERE id=21")
        first=self.quote(20,'creator-snapshot01',contact_phone='+998935551122')
        other=self.quote(21,'creator-other-0001',contact_phone='+998945552233')
        with self.s.db:self.s.db.execute("UPDATE users SET name='Changed' WHERE id=20")
        self.quote(20,'creator-new-phone1',contact_phone='+998955553344')
        repeat=self.quote(20,'creator-reuse-0001')
        self.assertEqual(self.s.one('quotes',first)['creator_name'],'First')
        self.assertEqual(self.s.one('quotes',first)['creator_phone'],'+998935551122')
        self.assertEqual(self.s.one('quotes',other)['creator_phone'],'+998945552233')
        self.assertEqual(self.s.one('quotes',repeat)['creator_phone'],'+998955553344')

    def test_missing_or_invalid_personal_number_creates_no_quote(self):
        with self.s.db:self.s.db.execute("DELETE FROM meta WHERE key='contact_phone:20'")
        for i,value in enumerate((None,'','abc','123','+000123456789','+998900000000x')):
            extra={} if value is None else {'contact_phone':value}
            with self.assertRaisesRegex(ValueError,'contact_phone'):
                self.quote(20,f'creator-invalid-{i:04}',**extra)
        self.assertEqual(self.s.rows('SELECT * FROM quotes'),[])
        self.assertEqual(self.s.stock(20)[0]['qty'],10)

    def test_personal_contact_is_printed_in_both_languages(self):
        with self.s.db:self.s.db.execute("UPDATE users SET name='Salesperson' WHERE id=20")
        ref=self.quote(20,'creator-print-0001',contact_phone='+998935551122')
        for lang in ('uz','ru'):
            with self.s.db:self.s.db.execute('UPDATE quotes SET lang=? WHERE id=?',(lang,ref))
            with patch('quotation.SimpleDocTemplate.build') as build:quotation_pdf(self.s,20,ref)
            story=build.call_args.args[0]
            text=' '.join(x.getPlainText() for x in story if hasattr(x,'getPlainText'))
            self.assertIn('Salesperson',text)
            self.assertIn('+998 93 555 11 22',text)
            self.assertIn('Tuzdi:' if lang=='uz' else 'Составил:',text)
            self.assertNotIn(COMPANY_PHONE,text)

    def test_four_tyre_quote_matches_reported_confirmation_and_retry_is_idempotent(self):
        with self.s.db:
            products=[self.s.product(10,'Haida '+name,price) for name,price in [('HD183','380'),('HD776','350'),('HD168','380'),('HD269','350')]]
        payload={'client':self.client,'items':[{'product':product,'qty':1,'price':price} for product,price in zip(products,['380','350','380','350'])],'payment':'naqd','fulfillment':'pickup','exchange_rate':'12000','contact_phone':'+998770690007'}
        first=self.service.write(20,'reported-four-tyres','quote',payload)
        second=self.service.write(20,'reported-four-tyres','quote',payload)
        self.assertEqual(first,second)
        self.assertEqual(len(self.s.rows('SELECT * FROM quotes')),1)
        quote=self.s.one('quotes',first['id'])
        self.assertEqual(quote['total'],1752000000)
        self.assertEqual(quote['creator_phone'],'+998770690007')
        self.assertEqual(len(self.s.rows('SELECT * FROM quote_items')),4)

    def test_phone_normalization(self):
        self.assertEqual(normalize_contact_phone('974788606'),'+998974788606')
        self.assertEqual(normalize_contact_phone('998974788606'),'+998974788606')
        self.assertEqual(normalize_contact_phone('+998 (97) 478-86-06'),'+998974788606')

class ChatQuoteCreatorTests(unittest.TestCase):
    setUp=bot_fixtures.TestCRM.setUp
    tearDown=bot_fixtures.TestCRM.tearDown
    msg=bot_fixtures.TestCRM.msg

    def test_chat_prompts_for_first_personal_number(self):
        from i18n import tr
        with self.s.db:self.s.db.execute("DELETE FROM meta WHERE key='contact_phone:20'")
        for value in ('/quote',str(self.client),f'{self.product} 1 380','naqd','pickup','12000'):
            self.msg(value)
        self.assertEqual(self.b.session(20)['step'],5)
        self.msg('93 555 11 22')
        self.msg(tr('confirm','uz'))
        self.assertIsNone(self.b.session(20))
        self.assertEqual(self.s.one('quotes',1)['creator_phone'],'+998935551122')
