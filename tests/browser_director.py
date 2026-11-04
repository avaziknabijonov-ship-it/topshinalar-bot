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
            s.db.execute("UPDATE users SET name='Test direktor' WHERE id=10")
            point=s.add('points',name='Test ombor');s.add('points',name='Test vitrina')
            product=s.product(10,'Test shina 315/80 R22.5','125.00');s.db.execute("UPDATE products SET size='315/80 R22.5' WHERE id=?",(product,))
            s.move(20,product,point,10,'in','Browser test fixture')
            s.client(20,'Test mijoz','+998900000001','','')
            s.supplier_save(10,'Test ta’minotchi')
        server=MiniServer(('127.0.0.1',0),path,TOKEN);port=server.server_address[1];server.origin=f'http://localhost:{port}'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(server.origin+'/director');page.locator('#start-login').click();expect(page.locator('#login-code')).to_contain_text('/cabinet_login')
                command=page.locator('#login-code').inner_text();auth.approve(s,10,command.split()[1]);s.db.commit()
                page.locator('#workspace').wait_for(state='visible');page.locator('.metric').first.wait_for();page.screenshot(path=str(screens/'director-desktop.png'),full_page=True)
                for section in ('sales','stock','clients','suppliers','managers','staff','reports','website','audit'):
                    page.locator('[data-section="'+section+'"]').click();expect(page.locator('#status')).not_to_contain_text('Yuklanmoqda')
                    status=page.locator('#status').inner_text();assert 'mavjud emas' not in status and 'tekshiring' not in status,(section,status)
                page.locator('[data-section="website"]').click();page.locator('tr[data-id]').first.click();page.locator('select[name="price_mode"]').select_option('website');page.locator('input[name="price"]').fill('125.00');page.locator('input[name="published"]').check();page.locator('input[name="points"]').first.check();page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                assert s.db.execute('SELECT price_cents FROM website_products').fetchone()[0]==12500
                page.screenshot(path=str(screens/'director-catalog.png'),full_page=True)
                page.locator('[data-section="stock"]').click();page.locator('#actions button').filter(has_text='Inventarizatsiya').click();page.locator('input[name="actual"]').fill('8');page.locator('input[name="reason"]').fill('Browser inventory test');page.locator('#operation button[type="submit"]').click();page.locator('#operation').get_by_text('Joriy: 10 · Haqiqiy: 8 · Farq: -2').wait_for();page.locator('#operation button[type="submit"]').click();page.locator('#detail').wait_for(state='hidden')
                assert s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?',(product,point)).fetchone()[0]==8
                page.locator('[data-section="overview"]').click();page.set_viewport_size({'width':390,'height':844});page.locator('.metric').first.wait_for();page.screenshot(path=str(screens/'director-mobile.png'),full_page=True)
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
            print(json.dumps({'browser':'Chromium','desktop':'1440x1000','mobile':'390x844','checks':'login approval, sections, USD settings, inventory preview/confirmation, RU, logout, Telegram initData without cookies','screenshots':3,'result':'passed'}))
        finally:server.shutdown();server.server_close();thread.join();s.db.close()

if __name__=='__main__':main()
