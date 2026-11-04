"""Chromium employee privacy + shared staff history view; disposable fixtures only."""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store,now
from miniapp import MiniServer
from test_miniapp import signed,TOKEN

def main():
 from playwright.sync_api import sync_playwright,expect
 screens=Path(__file__).resolve().parents[1]/'docs'/'screenshots'
 with tempfile.TemporaryDirectory() as temp:
  path=Path(temp)/'db';s=Store(path);s.configure([10],[20,21])
  with s.db:
   s.db.execute("UPDATE users SET name='Test menejer' WHERE id=20");s.db.execute("UPDATE users SET name='Boshqa menejer' WHERE id=21")
   point=s.add('points',name='Test ombor');product=s.product(10,'Test shina 315/80','125');s.move(20,product,point,100,'in','Fixture');shared=s.client(10,'Birgalikdagi mijoz','+998901234567','','');other=s.client(21,'Maxfiy boshqa mijoz','+998907654321','','')
   own=s.order(20,shared,[dict(product=product,qty=2,price='125')],point=point,paid='50',payment='card');s.set_debt_due(20,own,'2027-01-01');other_sale=s.order(21,shared,[dict(product=product,qty=1,price='999')],point=point,paid='1',payment='cash');s.order(21,other,[dict(product=product,qty=1,price='888')],point=point,paid='0',payment='cash')
  server=MiniServer(('127.0.0.1',0),path,TOKEN);server.origin='http://localhost:'+str(server.server_address[1]);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
    def context(uid):
     ctx=browser.new_context(viewport={'width':1440,'height':1000});ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort());ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(uid,query_id='sales-browser-'+str(uid),user=json.dumps({'id':uid,'first_name':'Test menejer' if uid==20 else 'Test direktor'})))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};');return ctx
    employee=context(20);page=employee.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(server.origin+'/');page.locator('[data-tab="dashboard"]').click();page.locator('[data-action="sales"]').click();expect(page.locator('#my-sales-view .es-sale')).to_have_count(1);expect(page.locator('#my-sales-view')).to_contain_text('200.00 USD');expect(page.locator('#my-sales-view')).to_contain_text('Test shina 315/80');assert '999.00' not in page.locator('#my-sales-view').inner_text();assert 'Maxfiy boshqa mijoz' not in page.locator('#my-sales-view').inner_text()
    page.locator('#my-sales-view .es-days summary').click();page.screenshot(path=str(screens/'employee-sales-desktop.png'),full_page=True)
    page.locator('#my-sales-view input[name="q"]').fill('Maxfiy');page.locator('#my-sales-view button[type="submit"]').click();expect(page.locator('.es-empty')).to_be_visible();page.locator('[data-es-clear]').click();expect(page.locator('.es-sale')).to_have_count(1)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(screens/'employee-sales-mobile.png'),full_page=True);page.locator('#my-sales-view .es-sale').scroll_into_view_if_needed();page.screenshot(path=str(screens/'employee-sales-mobile-detail.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    result=page.evaluate("async()=>{const r=await fetch('/api/my-sales?sale="+str(other_sale)+"',{headers:{'X-Telegram-Init-Data':Telegram.WebApp.initData}});return r.status;}");assert result==403
    page.locator('[data-close]').click();page.locator('[data-tab="clients"]').click();expect(page.locator('#app')).not_to_contain_text('Maxfiy');page.locator('[data-client-sales]').first.click();expect(page.locator('.es-sale')).to_have_count(1)
    page.locator('[data-close]').click();page.locator('#language').click();page.locator('[data-tab="dashboard"]').click();page.locator('[data-action="sales"]').click();expect(page.locator('#my-sales-view')).to_contain_text('Остаток долга');assert not errors,errors
    director=context(10);admin=director.new_page();admin.on('pageerror',lambda e:errors.append(str(e)));admin.goto(server.origin+'/director');admin.locator('#workspace').wait_for(state='visible');admin.locator('[data-section="staff"]').click();admin.locator('#content tr[data-id]').filter(has_text='Test menejer').click();admin.locator('#detail-content button').filter(has_text='Xodimning savdo tarixi').click();expect(admin.locator('#staff-sales-view .es-sale')).to_have_count(1);expect(admin.locator('#staff-sales-view')).to_contain_text('200.00 USD');admin.screenshot(path=str(screens/'staff-sales-history.png'),full_page=True)
    with s.db:s.db.execute('UPDATE users SET active=0 WHERE id=20')
    page.locator('[data-es-clear]').click();expect(page.locator('#my-sales-view [role="alert"]')).to_be_visible();assert not errors,errors
    browser.close()
   print(json.dumps({'result':'passed','checks':'employee own sales/client goods/debt/day view, shared-client isolation, tampered URL 403, search/empty/reset, RU, desktop/mobile, director selected employee, deactivation','screenshots':4}))
  finally:server.shutdown();server.server_close();thread.join();s.db.close()

if __name__=='__main__':main()
