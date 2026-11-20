"""Qarzlar section in real Chromium: customers' debts, what we owe suppliers, due dates.

Disposable fixtures only. SCREENSHOT_DIR may redirect captures. No Telegram API calls.
"""
import json
import os
from datetime import date,timedelta
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from browser_helpers import filters,section
from core import Store,now
from miniapp import MiniServer,MiniService,initialize
from test_miniapp import TOKEN,signed


def main():
    from playwright.sync_api import sync_playwright,expect
    screens=Path(os.environ.get('SCREENSHOT_DIR',Path(__file__).resolve().parents[1]/'docs'/'screenshots'))
    screens.mkdir(parents=True,exist_ok=True)
    today=now()[:10];ago=lambda d:(date.fromisoformat(today)-timedelta(days=d)).isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'debts.sqlite3';s=Store(path);s.configure([10],[20])
        with s.db:
            s.db.execute("UPDATE users SET name='Sinov direktori' WHERE id=10");s.db.execute("UPDATE users SET name='Sinov xodimi' WHERE id=20")
            point=s.add('points',name='Sinov ombori');client=s.client(20,'Sinov mijozi','+998900000001','','')
            vendor=s.supplier_save(10,'Sinov zavodi');product=s.product(10,'Haida · 315/80 R22.5','125.25')
        initialize(path);api=MiniService(s,'fixture')
        api.write(10,'browser-debts-receive','supplier_income',{'product':product,'supplier':vendor,'cost':'50','allocations':[{'point':point,'qty':4}],'currency':'USD','date':today})
        with s.db:
            sale=s.order(20,client,[dict(product=product,qty=2,price='125.25')],point=point,paid='50',payment='cash');s.set_debt_due(20,sale,ago(6))
        s.db.commit()
        server=MiniServer(('127.0.0.1',0),path,TOKEN);server.origin='http://localhost:'+str(server.server_address[1])
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
            errors=[]
            ctx=browser.new_context(viewport={'width':1440,'height':900})
            ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort())
            person=json.dumps({'id':10,'first_name':'Sinov direktori'})
            ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(10,query_id='debts-10',user=person))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};')
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(server.origin+'/director')
            section(page,'debts');expect(page.locator('#title')).to_have_text('Qarzlar')
            expect(page.locator('.debt-tab.active')).to_have_text('Mijozlar qarzi')
            expect(page.locator('tr[data-id]')).to_have_count(1)
            expect(page.locator('.chip.bad')).to_contain_text('Kechikmoqda 6 kun')
            expect(page.locator('.debt-totals')).to_contain_text('Jami mijozlar qarzi')
            expect(page.locator('td.due')).to_be_visible()
            page.screenshot(path=str(screens/'debts-clients.png'))
            # A customer row opens the sale with its debt actions.
            page.locator('tr[data-id]').click();expect(page.locator('#detail-content')).to_contain_text('Qarz to‘lovi')
            page.locator('#close-detail').click()
            # What we owe suppliers: set a past due date and see it overdue.
            page.locator('[data-debt-view="suppliers"]').click()
            expect(page.locator('.debt-tab.active')).to_have_text('Biz qarzmiz')
            expect(page.locator('tr[data-id]')).to_have_count(1)
            expect(page.locator('.debt-totals')).to_contain_text('Jami biz qarzmiz')
            expect(page.locator('.chip.bad')).to_have_count(0)
            page.locator('[data-due]').click()
            page.locator('#operation input[name="due"]').fill(ago(3));page.locator('#operation button[type="submit"]').click()
            page.locator('#detail').wait_for(state='hidden')
            expect(page.locator('.chip.bad')).to_contain_text('Kechikmoqda 3 kun')
            page.screenshot(path=str(screens/'debts-suppliers.png'))
            # Overdue filter keeps it; a far-future due date removes it.
            filters(page);page.locator('#section-filters select[name="overdue"]').select_option('1')
            expect(page.locator('tr[data-id]')).to_have_count(1)
            page.locator('[data-due]').click();page.locator('#operation input[name="due"]').fill(ago(-30));page.locator('#operation button[type="submit"]').click()
            page.locator('#detail').wait_for(state='hidden');expect(page.locator('.workspace-empty')).to_be_visible()
            # Phone width: no horizontal overflow.
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(screens/'debts-mobile.png'))
            browser.close()
        assert not errors,errors
    print(json.dumps({'result':'passed','checks':'customer debts with late chip and totals, sale opens, supplier payables, due date set and overdue filter, 390px','screenshots':3}))


if __name__=='__main__':
    main()
