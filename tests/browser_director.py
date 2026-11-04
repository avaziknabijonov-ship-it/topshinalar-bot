"""Optional real Chromium smoke check. Uses disposable fixtures, never production.
Run: python tests/browser_director.py (playwright + system chromium required).
"""
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store
from miniapp import MiniServer
import director_auth as auth
from test_miniapp import signed,TOKEN


def main():
    from playwright.sync_api import sync_playwright,expect
    root=Path(__file__).resolve().parents[1];screens=root/'docs'/'screenshots';screens.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'smoke.sqlite3';s=Store(path);s.configure([10],[20])
        with s.db:
            s.db.execute("UPDATE users SET name='Test direktor' WHERE id=10");s.db.execute("UPDATE users SET name='Test menejer' WHERE id=20")
            point=s.add('points',name='Test ombor');s.add('points',name='Test vitrina')
            product=s.product(10,'Test shina 315/80 R22.5','125.00');s.db.execute("UPDATE products SET size='315/80 R22.5' WHERE id=?",(product,))
            s.move(20,product,point,10,'in','Browser test fixture')
            s.client(20,'Test mijoz','+998900000001','','')
            supplier=s.supplier_save(10,'Test ta’minotchi')
            extra=s.product(10,'Test kirim shina','300');s.receive(20,extra,supplier,'250',[dict(point=point,qty=10)],'Test invoice',__import__('core').now()[:10],'USD');s.supplier_pay(10,supplier,'1000','cash');s.supplier_pay(10,supplier,'500','card')
        server=MiniServer(('127.0.0.1',0),path,TOKEN);port=server.server_address[1];server.origin=f'http://localhost:{port}'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(server.origin+'/director');page.locator('#start-login').click();expect(page.locator('#login-code')).to_contain_text('/cabinet_login')
                command=page.locator('#login-code').inner_text();auth.approve(s,10,command.split()[1]);s.db.commit()
                page.locator('#workspace').wait_for(state='visible');page.locator('.metric').first.wait_for(timeout=12000);page.screenshot(path=str(screens/'director-desktop.png'),full_page=True)
                for section in ('sales','stock','clients','suppliers','managers','staff','reports','website','audit'):
                    page.locator('[data-section="'+section+'"]').click();expect(page.locator('#status')).not_to_contain_text('Yuklanmoqda')
                    status=page.locator('#status').inner_text();assert 'mavjud emas' not in status and 'tekshiring' not in status,(section,status)
                page.locator('[data-section="clients"]').click();page.locator('#actions button').filter(has_text='Mijoz qo‘shish').click();page.locator('input[name="name"]').fill('Browser new client');page.locator('input[name="phone"]').fill('+998901234567');page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                page.locator('#search').fill('Browser new client');page.locator('#filters button[type="submit"]').click();expect(page.locator('tr[data-id]')).to_have_count(1);page.locator('tr[data-id]').click();page.locator('#edit-director-client').click();page.locator('input[name="name"]').fill('Browser renamed client');page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden');assert s.db.execute("SELECT COUNT(*) FROM clients WHERE name='Browser renamed client'").fetchone()[0]==1
                page.locator('#search').fill('');page.locator('[data-section="stock"]').click();page.locator('#section-filters select[name="point"]').select_option(str(point));expect(page.locator('#status')).not_to_contain_text('Yuklanmoqda');assert not page.locator('#content th').filter(has_text=re.compile('^ID$')).count();page.screenshot(path=str(screens/'director-stock-filters.png'),full_page=True)
                page.locator('[data-section="suppliers"]').click();page.locator('tr[data-id]').first.click();expect(page.locator('#detail-content')).to_contain_text('Qarz tarixi');page.screenshot(path=str(screens/'director-debt-history.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth');page.screenshot(path=str(screens/'director-debt-history-mobile.png'),full_page=True);page.locator('#close-detail').click();page.set_viewport_size({'width':1440,'height':1000})
                page.locator('[data-section="reports"]').click();page.locator('#report-all').uncheck();page.locator('[data-report-category="clients"]').check();page.locator('[data-report-category="suppliers"]').check();page.screenshot(path=str(screens/'director-report-categories.png'),full_page=True)
                with page.expect_download() as download:page.locator('#download-selected-report').click()
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth');page.screenshot(path=str(screens/'director-report-categories-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1000})
                target=Path(temp)/'selected.xlsx';download.value.save_as(target)
                from openpyxl import load_workbook
                exported=load_workbook(target);assert len(exported.sheetnames)==9,exported.sheetnames
                page.locator('[data-section="website"]').click();page.locator('tr[data-id]').first.click();page.locator('select[name="price_mode"]').select_option('website');page.locator('input[name="price"]').fill('125.00');page.locator('input[name="published"]').check();page.locator('input[name="points"]').first.check();page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                assert s.db.execute('SELECT price_cents FROM website_products').fetchone()[0]==12500
                page.screenshot(path=str(screens/'director-catalog.png'),full_page=True)
                page.locator('[data-section="stock"]').click();page.locator('#actions button').filter(has_text='Inventarizatsiya').click();page.locator('input[name="actual"]').fill('8');page.locator('input[name="reason"]').fill('Browser inventory test');page.locator('#operation button[type="submit"]').click();page.locator('#operation').get_by_text('Joriy: 10 · Haqiqiy: 8 · Farq: -2').wait_for();page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                assert s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?',(product,point)).fetchone()[0]==8
                from openpyxl import Workbook
                from reportlab.pdfgen.canvas import Canvas
                excel=Path(temp)/'receipt.xlsx';wb=Workbook();ws=wb.active;ws.append(['Nomi','Narx USD','Kelgan dona']);ws.append(['Browser Excel tire','125.25',3]);wb.save(excel)
                page.locator('#header-import').click();page.locator('#director-import-file').set_input_files(str(excel));page.locator('#director-import-upload button[type="submit"]').click();page.locator('#director-import-apply').wait_for()
                assert s.db.execute("SELECT COUNT(*) FROM products WHERE name='Browser Excel tire'").fetchone()[0]==0
                page.locator('#director-import-apply').click();expect(page.locator('.import-error')).to_contain_text('Avval');page.locator('#director-import-confirm').check();page.locator('#director-import-apply').click();page.locator('#detail').wait_for(state='hidden');expect(page.locator('#status')).to_contain_text('Kirim saqlandi')
                assert s.db.execute("SELECT price FROM products WHERE name='Browser Excel tire'").fetchone()[0]==12525
                pdf=Path(temp)/'receipt.pdf';canvas=Canvas(str(pdf));canvas.drawString(40,780,'Nomi | Kelgan dona | Narx USD');canvas.drawString(40,755,'Browser PDF tire | 2 | 50.00');canvas.save()
                page.locator('#header-import').click();page.locator('[data-import-kind="pdf"]').click();page.locator('#director-import-file').set_input_files(str(pdf));page.locator('#director-import-upload button[type="submit"]').click();page.locator('#director-import-rows').wait_for();page.locator('[data-field="qty"]').fill('4');page.locator('[data-field="price"]').fill('50.25');page.locator('#director-import-rows button[type="submit"]').click();page.locator('#director-import-apply').wait_for();page.screenshot(path=str(screens/'premium-import-preview.png'),full_page=True)
                assert s.db.execute("SELECT COUNT(*) FROM products WHERE name='Browser PDF tire'").fetchone()[0]==0
                page.locator('#director-import-confirm').check();page.locator('#director-import-apply').click();page.locator('#detail').wait_for(state='hidden');expect(page.locator('#status')).to_contain_text('Kirim saqlandi')
                assert s.db.execute("SELECT s.qty FROM stock s JOIN products p ON p.id=s.product WHERE p.name='Browser PDF tire'").fetchone()[0]==4
                assert s.db.execute("SELECT price FROM products WHERE name='Browser PDF tire'").fetchone()[0]==5025
                with s.db:s.order(20,1,[dict(product=product,qty=1,price='125')],point=point,paid='25',payment='cash')
                page.locator('[data-section="managers"]').click();expect(page.locator('#status')).not_to_contain_text('Yuklanmoqda');expect(page.locator('#content')).to_contain_text('25.00 USD')
                page.screenshot(path=str(screens/'manager-money-desktop.png'),full_page=True)
                page.locator('[data-section="overview"]').click();page.locator('.metric').first.wait_for();page.screenshot(path=str(screens/'premium-dashboard-desktop.png'),full_page=True);page.locator('[data-section="managers"]').click();expect(page.locator('#status')).not_to_contain_text('Yuklanmoqda')
                page.locator('#actions button').filter(has_text='Pul yozuvi').click();page.locator('#operation select[name="kind"]').select_option('accepted');page.locator('#operation select[name="manager"]').select_option('20');page.locator('input[name="amount"]').fill('25');page.locator('input[name="note"]').fill('Browser cash desk receipt');page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                page.locator('[data-close-manager="20"]').click();page.locator('input[name="note"]').fill('Browser verified closing');page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden');expect(page.locator('#content')).to_contain_text('Yopilgan')
                page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(screens/'manager-money-mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Manager money mobile overflow'
                page.locator('[data-section="overview"]').click();page.set_viewport_size({'width':390,'height':844});page.locator('.metric').first.wait_for();page.screenshot(path=str(screens/'director-mobile.png'),full_page=True);page.screenshot(path=str(screens/'premium-dashboard-mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile document overflow'
                page.locator('#language').click();page.locator('[data-section="overview"]').wait_for();assert page.locator('#title').inner_text()=='Обзор'
                page.locator('#logout').click();page.locator('#login').wait_for(state='visible')
                assert not errors,errors
                telegram_context=browser.new_context(viewport={'width':1000,'height':800})
                telegram_context.route('https://telegram.org/js/telegram-web-app.js',lambda route:route.abort())
                telegram_context.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(10,query_id='browser-cookie-free'))+'}};')
                telegram_page=telegram_context.new_page();telegram_page.goto(server.origin+'/director');telegram_page.locator('#workspace').wait_for(state='visible')
                telegram_context.clear_cookies()
                telegram_page.locator('[data-section="website"]').click();telegram_page.locator('tr[data-id]').first.wait_for()
                telegram_page.locator('#logout').click();telegram_page.locator('#login').wait_for(state='visible');telegram_context.close()
                browser.close()
            print(json.dumps({'browser':'Chromium','desktop':'1440x1000','mobile':'390x844','checks':'login approval, sections, USD settings, inventory preview/confirmation, RU, logout, Telegram initData without cookies, automatic received money, accepted cash, day closing, Excel preview/confirm, PDF extraction/edit/confirm, premium dashboard, named stock filters, client create/edit, chronological supplier debt, selected Excel categories','screenshots':13,'result':'passed'}))
        finally:server.shutdown();server.server_close();thread.join();s.db.close()

if __name__=='__main__':main()
