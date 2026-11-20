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
from browser_helpers import section
from core import Store,now
from miniapp import MiniServer,MiniService,initialize
from test_miniapp import TOKEN,signed


def main():
    from playwright.sync_api import sync_playwright,expect
    screens=Path(os.environ.get('SCREENSHOT_DIR',Path(__file__).resolve().parents[1]/'docs'/'screenshots'))
    screens.mkdir(parents=True,exist_ok=True)
    today=now()[:10];ago=lambda d:(date.fromisoformat(today)-timedelta(days=d)).isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'cash.sqlite3';s=Store(path);s.configure([10],[20])
        with s.db:
            s.db.execute("UPDATE users SET name='Sinov direktori' WHERE id=10");s.db.execute("UPDATE users SET name='Sinov xodimi' WHERE id=20")
        initialize(path);s.db.commit()
        MiniService(s,'f').write(10,'cash-browser-fund-00001','manager_record',{'manager':20,'kind':'fund','amount':'100','currency':'USD','note':'x','date':today})
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
            section(page,'cashbox');expect(page.locator('#title')).to_have_text('Kassa va kurs')
            page.wait_for_timeout(1000);expect(page.locator('tbody').first).to_contain_text('100.00')
            page.get_by_role('button',name='Kurs kiritish').click()
            page.locator('#operation input[name="rate"]').fill('12800');page.locator('#operation button[type="submit"]').click()
            page.locator('#detail').wait_for(state='hidden')
            expect(page.locator('#content')).to_contain_text('12800')
            page.screenshot(path=str(screens/'cashbox.png'))
            browser.close()
        assert not errors,errors
    print(json.dumps({'result':'passed','checks':'cashbox totals and rate history'}))


if __name__=='__main__':
    main()
