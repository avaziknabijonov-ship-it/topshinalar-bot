"""Premium workspace interactions in real Chromium; disposable fixtures only.

SCREENSHOT_DIR may redirect captures outside the repository. No Telegram API calls.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser_helpers import section
from core import Store
from miniapp import MiniServer
from test_miniapp import TOKEN,signed


def main():
    from playwright.sync_api import sync_playwright,expect
    screens=Path(os.environ.get('SCREENSHOT_DIR',Path(__file__).resolve().parents[1]/'docs'/'screenshots'))
    screens.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'preview.sqlite3';s=Store(path);s.configure([10],[20,21])
        with s.db:
            s.db.execute("UPDATE users SET name='Sinov direktori' WHERE id=10")
            s.db.execute("UPDATE users SET name='Sinov xodimi' WHERE id=20")
            s.db.execute("UPDATE users SET name='Sinov xodimi B' WHERE id=21")
            point=s.add('points',name='Sinov ombori')
            client=s.client(20,'Sinov mijozi','+998900000001','','')
            for i,(brand,size,price) in enumerate([('Haida','315/80 R22.5','125.25'),('Triangle','12.00 R20','210'),('Linglong','385/65 R22.5','280.50'),('Haida','295/80 R22.5','195')]):
                product=s.product(10,brand+' · '+size,price)
                s.db.execute('UPDATE products SET brand=?,size=? WHERE id=?',(brand,size,product))
                s.move(20,product,point,20,'in','Disposable browser fixture')
                s.order(20 if i<3 else 21,client,[dict(product=product,qty=i+1,price=price)],point=point,paid='50',payment='card')
        server=MiniServer(('127.0.0.1',0),path,TOKEN)
        server.origin='http://localhost:'+str(server.server_address[1])
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
                errors=[]
                def context(uid=None):
                    ctx=browser.new_context(viewport={'width':1440,'height':1080})
                    ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort())
                    if uid:
                        person={'id':uid,'first_name':'Sinov direktori' if uid==10 else 'Sinov xodimi'}
                        ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(uid,query_id='premium-browser-'+str(uid),user=json.dumps(person)))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};')
                    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    return ctx,page
                ctx,page=context(10);page.goto(server.origin+'/director')
                expect(page.locator('.metric')).to_have_count(4)
                expect(page.locator('.nav-group')).to_have_count(4)
                expect(page.locator('[data-section]')).to_have_count(17)
                expect(page.locator('[aria-current=page]')).to_have_attribute('data-section','overview')
                page.screenshot(path=str(screens/'workspace-premium-director-desktop.png'),full_page=False)
                # A failed list request must clear its skeleton and offer a working retry.
                pending=[];ctx.route('**/director-api/clients?*',lambda r:pending.append(r))
                section(page,'clients');expect(page.locator('#content')).to_have_attribute('aria-busy','true')
                expect(page.locator('.workspace-loading')).to_be_visible()
                assert pending
                pending.pop().fulfill(status=503,content_type='application/json',body=json.dumps({'error':'Sinov: aloqa uzildi'}))
                expect(page.locator('#status')).to_contain_text('aloqa uzildi')
                expect(page.locator('#content')).to_have_attribute('aria-busy','false')
                expect(page.locator('.workspace-loading')).to_have_count(0)
                ctx.unroute('**/director-api/clients?*')
                page.locator('#actions button').filter(has_text='Qayta urinish').click()
                expect(page.locator('#content tr[data-id]')).to_have_count(1)
                row=page.locator('#content tr[data-id]').first;row.focus();page.keyboard.press('Enter')
                expect(page.locator('#detail')).to_be_visible();page.keyboard.press('Escape')
                page.locator('#search').fill('not-a-customer');page.locator('#filters button').click()
                expect(page.locator('#content .workspace-empty')).to_be_visible()
                page.locator('#search').fill('');section(page,'overview')
                # Drawer focus containment, Escape, navigation, breakpoints and scroll.
                page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('#menu-toggle')).to_be_visible()
                assert page.locator('#sidebar').evaluate('(el)=>el.inert')
                page.locator('#menu-toggle').click()
                expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','true')
                assert page.locator('#director-main').evaluate('(el)=>el.inert')
                page.locator('#logout').focus();page.keyboard.press('Tab')
                expect(page.locator('#sidebar .brand')).to_be_focused()
                page.keyboard.press('Shift+Tab');expect(page.locator('#logout')).to_be_focused()
                expect(page.locator('#sidebar')).to_have_css('transform','matrix(1, 0, 0, 1, 0, 0)')
                page.screenshot(path=str(screens/'workspace-premium-mobile-menu.png'),full_page=False)
                page.keyboard.press('Escape');expect(page.locator('#menu-toggle')).to_be_focused()
                assert not page.locator('#director-main').evaluate('(el)=>el.inert')
                section(page,'stock');expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','false')
                expect(page.locator('#title')).to_have_text('Ombor / vitrina')
                page.locator('#menu-toggle').click();page.set_viewport_size({'width':1440,'height':1080})
                expect(page.locator('#director-main')).to_have_js_property('inert',False)
                expect(page.locator('#sidebar')).to_have_js_property('inert',False)
                section(page,'reports');page.screenshot(path=str(screens/'workspace-premium-reports-desktop.png'),full_page=True)
                section(page,'overview');page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('.metric')).to_have_count(4)
                expect(page.locator('#sidebar')).to_have_css('visibility','hidden')
                page.screenshot(path=str(screens/'workspace-premium-director-mobile.png'),full_page=False)
                for width in (320,390,768,900,1024,1440):
                    page.set_viewport_size({'width':width,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),('director overflow',width)
                page.set_viewport_size({'width':390,'height':844});page.locator('#menu-toggle').click();page.locator('#language').click()
                expect(page.locator('#title')).to_have_text('Обзор')
                page.locator('#menu-toggle').click();expect(page.locator('#nav')).to_contain_text('Контроль денег')
                page.locator('#logout').click();expect(page.locator('#login')).to_be_visible()
                expect(page.locator('#menu-toggle')).to_be_hidden()
                assert not page.locator('#director-main').evaluate('(el)=>el.inert')
                # Employee UI retains own-only history, collection and catalogue actions.
                employee,work=context(20);work.goto(server.origin+'/')
                expect(work.locator('.product')).to_have_count(4)
                expect(work.locator('.product').filter(has_text='125.25')).to_have_count(1)
                expect(work.locator('#director-link')).to_be_hidden()
                expect(work.locator('#workspace-user')).to_have_text('Sinov xodimi')
                work.screenshot(path=str(screens/'workspace-premium-employee-catalog.png'),full_page=True)
                work.locator('[data-tab=dashboard]').click();expect(work.locator('.stats')).to_be_visible()
                work.screenshot(path=str(screens/'workspace-premium-employee-desktop.png'),full_page=True)
                work.set_viewport_size({'width':390,'height':844})
                work.screenshot(path=str(screens/'workspace-premium-employee-mobile.png'),full_page=False)
                work.locator('[data-action=sales]').click()
                expect(work.locator('.es-sale')).to_have_count(3)
                expect(work.locator('[data-es-collect]')).to_have_count(3)
                work.locator('[data-close]').click();work.locator('[data-tab=catalog]').click()
                for width in (320,390,768,1440):
                    work.set_viewport_size({'width':width,'height':844})
                    assert work.evaluate('document.documentElement.scrollWidth <= innerWidth'),('employee overflow',width)
                # CSS and shell assets do not grant employees access to director data.
                work.goto(server.origin+'/director');expect(work.locator('#login')).to_be_visible()
                expect(work.locator('#workspace')).to_be_hidden()
                assert not errors,errors
                browser.close()
            print(json.dumps({'result':'passed','checks':'17 grouped sections, loading/failure/retry, keyboard details, empty search, modal navigation focus/Escape/breakpoints, UZ/RU/logout, employee catalogue and own-only collection history, no director access, 320–1440px no overflow','screenshots':7}))
        finally:
            server.shutdown();server.server_close();thread.join();s.db.close()


if __name__=='__main__':main()
