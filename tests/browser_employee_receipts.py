"""Actual employee debt collection incl. committed response loss; temp DB only."""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store
from miniapp import MiniServer
from test_miniapp import TOKEN,signed


def main():
 from playwright.sync_api import sync_playwright,expect
 screens=Path(__file__).resolve().parents[1]/'docs'/'screenshots'
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'db';s=Store(path);s.configure([10],[20,21])
  with s.db:
   point=s.add('points',name='Test ombor');product=s.product(10,'Test shina','125');s.move(20,product,point,10,'in','Fixture');client=s.client(20,'Test mijoz','+998901234567','','');sale=s.order(20,client,[dict(product=product,qty=2,price='125')],point=point,paid='50',payment='card');other=s.order(21,client,[dict(product=product,qty=1,price='125')],point=point,paid='0',payment='cash')
  server=MiniServer(('127.0.0.1',0),path,TOKEN);server.origin='http://localhost:'+str(server.server_address[1]);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1440,'height':1000});ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort());ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(20,query_id='employee-receipt-browser'))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(server.origin+'/');page.locator('[data-tab="dashboard"]').click();page.locator('[data-action="sales"]').click();expect(page.locator('[data-es-collect]')).to_have_count(1)
    page.locator('[data-es-collect]').click();page.locator('.debt-collection-form input[name="amount"]').fill('201');page.locator('.debt-collection-form button[type="submit"]').click();expect(page.locator('.debt-error')).to_contain_text('qarzdan oshirmasdan');assert s.one('sales',sale)['paid']==5000
    page.locator('.debt-collection-form input[name="amount"]').fill('50.25');page.locator('.debt-collection-form button[type="submit"]').click();expect(page.locator('.debt-review')).to_contain_text('149.75 USD');page.screenshot(path=str(screens/'employee-debt-confirm-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.locator('.debt-review').scroll_into_view_if_needed();page.screenshot(path=str(screens/'employee-debt-confirm-mobile.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    keys=[]
    def intercept(route):
     body=route.request.post_data_json
     if body.get('cmd')!='collect_debt':route.continue_();return
     keys.append(route.request.headers['idempotency-key'])
     if len(keys)==1:
      response=route.fetch();assert response.status==200;route.abort()
     else:route.continue_()
    ctx.route('**/api/action',intercept)
    page.locator('[data-debt-confirm]').click();expect(page.locator('.es-receipt')).to_contain_text('149.75 USD',timeout=15000);assert len(keys)==2 and keys[0]==keys[1];assert s.one('sales',sale)['paid']==10025;assert len(s.rows('SELECT * FROM payments WHERE sale=?',(sale,)))==2
    page.locator('[data-close]').click();page.locator('[data-tab="debts"]').click();page.locator('[data-pay]').click();page.locator('#debt-collection-root input[name="amount"]').fill('49.75');page.locator('#debt-collection-root select').select_option('card');page.locator('#debt-collection-root button[type="submit"]').click();expect(page.locator('.debt-review')).to_contain_text('100.00 USD');page.locator('[data-debt-confirm]').click();page.locator('#modal').wait_for(state='hidden');assert s.one('sales',sale)['paid']==15000
    page.locator('[data-tab="dashboard"]').click();page.locator('[data-action="sales"]').click();page.locator('[data-es-collect]').click();page.locator('.debt-collection-form input[name="amount"]').fill('100');page.locator('.debt-collection-form select').select_option('transfer');page.locator('.debt-collection-form button[type="submit"]').click();page.locator('[data-debt-confirm]').click();expect(page.locator('.es-receipt')).to_contain_text('Qolgan qarz: 0.00 USD');expect(page.locator('[data-es-collect]')).to_have_count(0);assert s.one('sales',sale)['paid']==25000;assert s.one('sales',other)['paid']==0
    assert len(s.rows('SELECT * FROM payments WHERE sale=?',(sale,)))==4;assert s.manager_account(10,20)['balances'][0]['received']==25000
    page.locator('.es-receipt').scroll_into_view_if_needed();page.screenshot(path=str(screens/'employee-debt-saved-mobile.png'),full_page=True)
    page.locator('[data-close]').click();page.locator('#language').click();page.locator('[data-tab="dashboard"]').click();page.locator('[data-action="sales"]').click();expect(page.locator('#my-sales-view')).to_contain_text('История оплат')
    assert not errors,errors;browser.close()
   print(json.dumps({'result':'passed','checks':'own history and debt entry, overpayment preview rejected, cash/card/bank, exact remaining, committed response loss same-key retry once, zero debt hides action, RU, desktop/mobile','screenshots':3}))
  finally:server.shutdown();server.server_close();thread.join();s.db.close()

if __name__=='__main__':main()
