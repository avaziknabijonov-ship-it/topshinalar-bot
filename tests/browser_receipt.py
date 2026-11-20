"""Receipt PDFs, payment status bar and the 4-piece kit button in real Chromium.

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
        path=Path(tmp)/'rc.sqlite3';s=Store(path);s.configure([10],[20])
        with s.db:
            s.db.execute("UPDATE users SET name='Sinov direktori' WHERE id=10");s.db.execute("UPDATE users SET name='Sinov xodimi' WHERE id=20")
            point=s.add('points',name='Sinov ombori');client=s.client(20,'Sinov mijozi','+998900000001','','')
            vendor=s.supplier_save(10,'Sinov zavodi');product=s.product(10,'Haida · 315/80 R22.5','125.25')
        initialize(path);s.db.commit()
        with s.db:
            s.move(20,product,point,10,'in','')
            sale=s.order(20,client,[dict(product=product,qty=2,price='125.25')],point=point,paid='50',payment='cash')
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
            section(page,'sales')
            expect(page.locator('progress.paybar.part')).to_have_count(1)
            expect(page.locator('.paycell')).to_contain_text('Qisman')
            page.screenshot(path=str(screens/'sales-paybar.png'))
            page.locator('tr[data-id]').click()
            for label,fmt in (('Chek A4 · PDF','a4'),('Chek 80 mm · PDF','80mm')):
                with page.expect_download() as d:page.get_by_role('button',name=label).click()
                target=Path(tmp)/('chek-'+fmt+'.pdf');d.value.save_as(target);assert target.read_bytes().startswith(b'%PDF-')
            page.get_by_role('button',name='Chek — Telegramga').click()
            expect(page.get_by_role('button',name='Yuborildi ✓')).to_be_visible()
            assert s.db.execute("SELECT COUNT(*) FROM outbox WHERE payload LIKE '%document%'").fetchone()[0]==1
            # Employee Mini App: 4-piece kit button.
            emp=ctx.new_page();emp.on('pageerror',lambda e:errors.append(str(e)))
            ctx2=browser.new_context(viewport={'width':390,'height':844});ctx2.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort())
            ctx2.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(20,query_id='rc-20'))+',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{onClick(){},show(){},hide(){}}}};')
            emp=ctx2.new_page();emp.on('pageerror',lambda e:errors.append(str(e)))
            emp.goto(server.origin+'/');expect(emp.locator('.product').first).to_be_visible(timeout=15000)
            emp.locator('[data-add="'+str(product)+'"]').first.click();emp.locator('#nav [data-tab="cart"]').click()
            emp.locator('[data-kit]').click();expect(emp.locator('input[data-qty]')).to_have_value('4')
            emp.screenshot(path=str(screens/'cart-kit.png'))
            browser.close()
        assert not errors,errors
    print(json.dumps({'result':'passed','checks':'paybar, A4/80mm PDF download, Telegram send queued, kit button'}))


if __name__=='__main__':
    main()
