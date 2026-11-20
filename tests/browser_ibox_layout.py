"""Director cabinet layout: collapsible menu groups, folded filters, totals row, compact rail.

Disposable fixtures only. SCREENSHOT_DIR may redirect captures. No Telegram API calls.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from browser_helpers import section,filters
from core import Store
from miniapp import MiniServer
from test_miniapp import TOKEN,signed


def main():
    from playwright.sync_api import sync_playwright,expect
    screens=Path(os.environ.get('SCREENSHOT_DIR',Path(__file__).resolve().parents[1]/'docs'/'screenshots'))
    screens.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'layout.sqlite3';s=Store(path);s.configure([10],[20])
        with s.db:
            s.db.execute("UPDATE users SET name='Sinov direktori' WHERE id=10")
            s.db.execute("UPDATE users SET name='Sinov xodimi' WHERE id=20")
            point=s.add('points',name='Sinov ombori')
            client=s.client(20,'Sinov mijozi','+998900000001','','')
            for i,(brand,size,price) in enumerate([('Haida','315/80 R22.5','125.25'),('Triangle','12.00 R20','210')]):
                product=s.product(10,brand+' · '+size,price)
                s.db.execute('UPDATE products SET brand=?,size=? WHERE id=?',(brand,size,product))
                s.move(20,product,point,20,'in','Disposable browser fixture')
                s.order(20,client,[dict(product=product,qty=i+1,price=price)],point=point,paid='50',payment='card')
        server=MiniServer(('127.0.0.1',0),path,TOKEN)
        server.origin='http://localhost:'+str(server.server_address[1])
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
            errors=[]
            ctx=browser.new_context(viewport={'width':1440,'height':900})
            ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort())
            person=json.dumps({'id':10,'first_name':'Sinov direktori'})
            ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(10,query_id='layout-10',user=person))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};')
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(server.origin+'/director')
            # Menu groups: only the active group is open, the rest fold and open on click.
            expect(page.locator('.nav-group-label[aria-expanded=true]')).to_have_count(1)
            money=page.locator('[data-group="2"]')
            expect(money).to_have_attribute('aria-expanded','false')
            expect(page.locator('[data-section="payments"]')).to_be_hidden()
            money.click();expect(page.locator('[data-section="payments"]')).to_be_visible()
            money.click();expect(page.locator('[data-section="payments"]')).to_be_hidden()
            section(page,'sales')  # helper opens a folded group when needed
            section(page,'payments');expect(page.locator('[data-section="payments"][aria-current=page]')).to_have_count(1)
            # Filters are folded until opened; the table starts higher.
            section(page,'sales');expect(page.locator('tr[data-id]')).to_have_count(2)
            expect(page.locator('#section-filters')).to_be_hidden()
            toggle=page.locator('#filter-toggle');expect(toggle).to_have_attribute('aria-expanded','false')
            filters(page);expect(page.locator('#section-filters')).to_be_visible()
            page.locator('#section-filters select[name="payment_status"]').select_option('debt')
            expect(toggle).to_contain_text('1');expect(page.locator('tr[data-id]')).to_have_count(2)
            # Debt is highlighted, money is right-aligned, page totals are shown per currency.
            expect(page.locator('td.due').first).to_be_visible()
            expect(page.locator('td.num').first).to_be_visible()
            expect(page.locator('tfoot .totals-row')).to_have_count(1)
            expect(page.locator('tfoot .totals-row')).to_contain_text('USD')
            expect(page.locator('.chip.ok').first).to_be_visible()
            # Total sits with the pagination under the list.
            assert page.evaluate("document.querySelector('.list-footer #status')&&document.querySelector('.list-footer .pagination')")
            page.screenshot(path=str(screens/'layout-director-sales.png'))
            # Compact rail keeps every section reachable and saves width.
            before=page.locator('#director-main').bounding_box()['x']
            page.locator('#rail-toggle').click()
            after=page.locator('#director-main').bounding_box()['x']
            assert after<before-150,(before,after)
            expect(page.locator('[data-section="payments"]')).to_be_visible()
            page.locator('[data-section="payments"]').click();expect(page.locator('#title')).to_have_text('Savdo tushumlari')
            page.screenshot(path=str(screens/'layout-director-rail.png'))
            page.reload();expect(page.locator('body.rail')).to_have_count(1)
            page.locator('#rail-toggle').click();expect(page.locator('body.rail')).to_have_count(0)
            # Phone width: no horizontal overflow, menu groups still work in the drawer.
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.locator('#menu-toggle').click()
            page.locator('.nav-group-label').nth(1).click()
            expect(page.locator('[data-section="products"]')).to_be_visible()
            page.screenshot(path=str(screens/'layout-director-mobile-menu.png'))
            browser.close()
        assert not errors,errors
    print(json.dumps({'result':'passed','checks':'folding menu groups, folded filters with count, debt/chip/totals, footer total, compact rail persisted, 390px menu','screenshots':3}))


if __name__=='__main__':
    main()
