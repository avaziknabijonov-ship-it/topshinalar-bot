import io
import json
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from core import Store,now
from miniapp import MiniServer
from test_miniapp import TOKEN,signed
from ui_text import CATALOG,FIELDS,language,value,browser_script


class LocalizationTests(unittest.TestCase):
    def test_all_catalog_entries_have_both_languages(self):
        def pair(item):
            self.assertIsInstance(item,list)
            self.assertEqual(len(item),2)
            self.assertTrue(all(isinstance(v,str) and v.strip() for v in item))
        for group in ('fields','actions','ui'):
            for item in CATALOG[group].values():pair(item)
        for choices in CATALOG['values'].values():
            for item in choices.values():pair(item)

    def test_coded_fields_translate_but_names_notes_and_money_are_unchanged(self):
        self.assertEqual(value('status','draft','ru'),'Черновик')
        self.assertEqual(value('role','employee','uz'),'Xodim')
        self.assertEqual(value('sync_status','pending','ru'),'В очереди')
        self.assertEqual(value('day_status','open','uz'),'Yopilmagan')
        self.assertEqual(value('source','payment','ru'),'Оплата')
        for lang in ('uz','ru'):
            for key,item in [('name','Triangle'),('note','Customer note in English'),('amount',12500),('currency','UZS')]:
                self.assertEqual(value(key,item,lang),item)

    def test_audit_payload_is_not_shown_as_json_or_english(self):
        self.assertEqual(value('action','supplier_edit:{"before":{"name":"private"}}','ru'),'Изменён поставщик')
        self.assertEqual(value('action','unknown_future_action:{"token":"secret"}','uz'),'Boshqa amal')

    def test_historical_payment_labels_and_custom_methods_are_preserved(self):
        from reports import localized
        self.assertEqual(localized('payment','ОПЛАТА КАРТОЙ','ru'),'ОПЛАТА КАРТОЙ')
        self.assertEqual(value('method','ОПЛАТА КАРТОЙ','ru'),'Карта')
        self.assertEqual(value('method','custom legacy method','uz'),'custom legacy method')

    def test_unknown_status_and_sync_failure_have_localized_fallbacks(self):
        self.assertEqual(value('status','new_future_state','ru'),'Не определено')
        self.assertNotIn('Sync failed',value('last_error','Sync failed; check receiver availability and configuration','uz'))

    def test_excel_errors_keep_compatibility_and_offer_a_single_language(self):
        from excel_import import fail,ExcelError
        with self.assertRaises(ExcelError) as caught:fail('Faylni tekshiring','Проверьте файл')
        self.assertIn('Faylni tekshiring',str(caught.exception))
        self.assertEqual(caught.exception.localized('ru'),'Excel: Проверьте файл')
        self.assertEqual(caught.exception.localized('uz'),'Excel: Faylni tekshiring')

    def test_language_allowlist_and_generated_asset(self):
        self.assertEqual(language('en','ru'),'ru')
        self.assertEqual(language('ru','uz'),'ru')
        self.assertEqual(language('ru\nX-Injected: yes'),'uz')
        script=browser_script()
        self.assertIn('window.WorkspaceTextData=',script)
        self.assertNotIn('BOT_TOKEN',script)

    def test_bot_accepts_translated_statuses_and_legacy_codes(self):
        from bot import Bot
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/'db');s.configure([10],[20]);b=Bot(s)
            try:
                for lang in ('uz','ru'):
                    with s.db:s.db.execute('UPDATE users SET lang=? WHERE id=20',(lang,))
                    for cmd,codes in [('quote_status',['draft','sent','accepted','rejected']),('delivery_status',['new','on_way','delivered','cancelled'])]:
                        for code in codes:
                            translated=CATALOG['values']['status'][code][lang=='ru']
                            self.assertEqual(b.validate(20,cmd,'status',translated,{}),code)
                            self.assertEqual(b.validate(20,cmd,'status',code,{}),code)
                        state={'cmd':cmd,'step':1,'data':{'ref':1}}
                        b.prompt(20,state)
                        payload=json.loads(s.rows('SELECT payload FROM outbox ORDER BY id DESC LIMIT 1')[0]['payload'])
                        buttons=[r[0]['text'] for r in payload['reply_markup']['keyboard'][:4]]
                        self.assertEqual(buttons,[CATALOG['values']['status'][c][lang=='ru'] for c in codes])
            finally:s.db.close()

    def test_bot_record_amounts_use_cents_and_localized_status(self):
        from bot import Bot
        message=Bot.pretty_row(None,{'amount':12500,'paid':5000,'currency':'USD','status':'draft'},'ru')
        self.assertIn('125.00 USD',message);self.assertIn('50.00 USD',message)
        self.assertIn('Черновик',message);self.assertNotIn('draft',message)


class LocalizationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db'
        self.s=Store(self.path);self.s.configure([10],[20])
        with self.s.db:
            self.point=self.s.add('points',name='Ombor')
            self.product=self.s.product(10,'Haida','125.00')
            self.client=self.s.client(20,'Mijoz','+998901234567','','English customer note')
            self.s.move(20,self.product,self.point,20,'in','Kirim')
            self.sale=self.s.order(20,self.client,[dict(product=self.product,qty=1,price='125')],point=self.point,paid='25',payment='card')
        self.server=MiniServer(('127.0.0.1',0),self.path,TOKEN)
        self.base='http://127.0.0.1:'+str(self.server.server_address[1]);self.server.origin=self.base
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.raw={uid:signed(uid,query_id='locale-http-'+str(uid)) for uid in (10,20)}
        import director_auth
        director_auth.telegram(self.s,self.raw[10],TOKEN)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.s.db.close();self.temp.cleanup()

    def request(self,path,body=None,lang='uz',uid=10):
        headers={'X-Telegram-Init-Data':self.raw[uid], 'X-Director-Nonce':secrets.token_hex(16),'X-UI-Language':lang,'Origin':self.base,'Content-Type':'application/json','Idempotency-Key':secrets.token_hex(16)}
        req=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with urlopen(req) as r:return r.status,r.read()
        except HTTPError as e:return e.code,e.read()

    def test_interface_language_controls_excel_independently_of_account_language(self):
        for lang,word in [('ru','Клиент'),('uz','Mijoz')]:
            status,raw=self.request('/director-api/report?categories=sales',lang=lang)
            self.assertEqual(status,200)
            wb=load_workbook(io.BytesIO(raw))
            self.assertIn(word,[c.value for c in wb.worksheets[0][1]])
        self.assertEqual(self.s.user(10)['lang'],'uz')
        self.assertEqual(self.s.one('sales',self.sale)['paid'],2500)

    def test_invalid_language_falls_back_to_authenticated_language(self):
        with self.s.db:self.s.db.execute("UPDATE users SET lang='ru' WHERE id=10")
        status,raw=self.request('/director-api/report?categories=clients',lang='en')
        self.assertEqual(status,200)
        self.assertIn('Клиенты',load_workbook(io.BytesIO(raw)).sheetnames[0])

    def test_russian_template_round_trips_through_existing_import_parser(self):
        from excel_import import InventoryExcel
        status,raw=self.request('/director-api/import-template',lang='ru')
        self.assertEqual(status,200);wb=load_workbook(io.BytesIO(raw));ws=wb.active
        self.assertEqual(ws.title,'Приход');self.assertIn('Название',[c.value for c in ws[1]])
        ws.append([None,'Новая шина','Haida','315/80 R22.5','125.25',3,None])
        out=io.BytesIO();wb.save(out)
        # Reuse the actual public parser; template translation cannot change semantics.
        import base64
        data={'point':self.point,'file':base64.b64encode(out.getvalue()).decode(),'mode':'income'}
        from miniapp import MiniService
        preview=MiniService(self.s,TOKEN).write(10,'russian-template-preview','excel_preview',data)
        self.assertEqual(preview['id']['rows'][0]['price'],12525)
        self.assertEqual(preview['id']['rows'][0]['qty'],3)

    def test_error_locale_and_header_never_grant_employee_access(self):
        for lang,word in [('ru','Доступ запрещён'),('uz','Kirish rad etildi')]:
            status,raw=self.request('/director-api/sales',lang=lang,uid=20)
            self.assertEqual(status,403);self.assertIn(word,json.loads(raw)['error'])
        self.assertEqual(self.s.one('sales',self.sale)['paid'],2500)

    def test_excel_validation_is_single_language(self):
        for lang,forbidden in [('ru','fayl'),('uz','файл')]:
            status,raw=self.request('/director-api/action',{'cmd':'excel_preview','data':{'point':self.point,'file':'broken','mode':'income'}},lang=lang)
            self.assertEqual(status,400)
            self.assertNotIn(forbidden,json.loads(raw)['error'].lower())

    def test_new_asset_is_public_labels_only_and_no_business_rows(self):
        with urlopen(self.base+'/ui-text.js') as r:
            self.assertIn('javascript',r.headers['Content-Type']);text=r.read().decode()
        self.assertTrue(text.startswith('window.WorkspaceTextData='))
        self.assertNotIn('English customer note',text)
        self.assertNotIn('+998901234567',text)

    def test_all_report_fields_have_localized_labels(self):
        from director_reports import build
        from reports import COLUMNS,SECTIONS
        data=build(self.s,10,{'categories':'all','start':now()[:10],'end':now()[:10]})
        self.assertFalse(set(data)-set(SECTIONS))
        missing={key for rows in data.values() for row in rows for key in row if key not in COLUMNS}
        self.assertEqual(missing,set())


if __name__=='__main__':unittest.main()
