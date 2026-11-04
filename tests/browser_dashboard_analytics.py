"""Real Chromium checks of two dashboard analyses; disposable business fixtures."""
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
  path=Path(tmp)/'db';s=Store(path);s.configure([10],[20,21]);products=[]
  with s.db:
   s.db.execute("UPDATE users SET name='Test menejer A' WHERE id=20");s.db.execute("UPDATE users SET name='Test menejer B' WHERE id=21")
   point=s.add('points',name='Test ombor');client=s.client(20,'Test mijoz','+998901234567','','')
   for i in range(1,13):
    product=s.product(10,'Analitika shina '+str(i).zfill(2),str(10+i));products.append(product);s.move(20,product,point,100,'in','Fixture');s.order(20 if i<=10 else 21,client,[dict(product=product,qty=i,price=str(10+i))],point=point,paid='5',payment='card')
   legacy=s.order(20,client,[dict(product=products[0],qty=1,price='50')],point=point,paid='0',payment='cash');s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(legacy,))
   cancel=s.order(21,client,[dict(product=products[0],qty=1,price='10')],point=point,paid='5',payment='cash');s.cancel_sale(10,cancel,'Browser cancelled fixture',refund_confirmed=True)
  server=MiniServer(('127.0.0.1',0),path,TOKEN);server.origin='http://localhost:'+str(server.server_address[1]);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1440,'height':1100});ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort());ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(10,query_id='analytics-browser'))+'}};');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(server.origin+'/director')
    products_box=page.locator('[data-analytics-card="products"]');employees_box=page.locator('[data-analytics-card="employees"]');expect(products_box.locator('.analytic-rank')).to_have_count(5);expect(employees_box.locator('.analytic-rank')).to_have_count(2);expect(products_box.locator('tbody tr')).to_have_count(10);products_box.locator('.analytics-details>summary').click()
    products_box.locator('[data-analytics-next]').click();expect(products_box.locator('tbody tr')).to_have_count(2);products_box.locator('[data-analytics-prev]').click()
    products_box.locator('input[name="q"]').fill('Analitika shina 01');products_box.locator('button[type="submit"]').click();expect(products_box.locator('tbody tr')).to_have_count(1);products_box.locator('[data-analytics-currency]').select_option('UZS');expect(products_box).to_contain_text('50.00 UZS');expect(employees_box.locator('tbody')).not_to_contain_text('UZS');expect(employees_box.locator('[data-analytics-currency]')).to_have_value('USD')
    products_box.locator('[data-analytics-currency]').select_option('USD');products_box.locator('input[name="q"]').fill('');products_box.locator('button[type="submit"]').click();products_box.locator('[data-analytics-metric]').select_option('revenue');expect(products_box.locator('.analytics-caption')).to_contain_text('Savdo summasi')
    products_box.locator('.analytic-rank').first.click();expect(page.locator('#title')).to_have_text('Savdolar');expect(page.locator('#section-filters select[name="product"]')).to_have_value(str(products[-1]));expect(page.locator('#section-filters select[name="currency"]')).to_have_value('USD');expect(page.locator('#content')).to_contain_text('butun savdolar')
    page.locator('[data-section="overview"]').click();expect(employees_box.locator('.analytic-rank')).to_have_count(2);employees_box.locator('[data-analytics-metric]').select_option('debt_to_date');employees_box.locator('.analytic-rank').first.click();expect(page.locator('#section-filters select[name="manager"]')).to_have_value('20');expect(page.locator('#status')).to_contain_text('Jami: 10')
    page.locator('[data-section="overview"]').click();expect(products_box.locator('tbody tr')).to_have_count(10);products_box.locator('.analytics-details>summary').click();page.screenshot(path=str(screens/'dashboard-two-analytics-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(screens/'dashboard-two-analytics-mobile.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#language').click();expect(page.locator('[data-analytics-card="products"]')).to_contain_text('Аналитика по товарам');expect(page.locator('[data-analytics-card="employees"]')).to_contain_text('Аналитика по сотрудникам')
    page.locator('#start').fill('2000-01-01');page.locator('#end').fill('2000-01-01');page.locator('#filters button[type="submit"]').click();expect(page.locator('.analytic-rank')).to_have_count(0);expect(page.locator('[data-analytics-card="products"]')).to_contain_text('Нет данных')
    assert not errors,errors;browser.close()
   print(json.dumps({'result':'passed','checks':'two real analyses, product/staff ranks, metric/currency/search, pagination, exact product/employee sales drill-down, mobile no overflow, RU and empty period','screenshots':2}))
  finally:server.shutdown();server.server_close();thread.join();s.db.close()

if __name__=='__main__':main()
