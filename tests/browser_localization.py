"""UZ/RU UI and reliability checks against a disposable business database."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser_helpers import section,menu
from core import Store,now
from miniapp import MiniServer
from test_miniapp import TOKEN,signed


def main():
    from playwright.sync_api import sync_playwright,expect
    screens=Path(os.environ.get('SCREENSHOT_DIR',Path(__file__).resolve().parents[1]/'docs'/'screenshots'));screens.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'db';s=Store(path);s.configure([10],[20,21])
        with s.db:
            s.db.execute("UPDATE users SET name='Direktor' WHERE id=10")
            s.db.execute("UPDATE users SET name='Menejer' WHERE id=20")
            point=s.add('points',name='Markaziy ombor');product=s.product(10,'Haida 315/80 R22.5','125')
            client=s.client(20,'Mijoz','+998901234567','','')
            supplier=s.supplier_save(10,'Ta’minotchi');receipt=s.receive(20,product,supplier,'80',[dict(point=point,qty=20)],'Kirim')
            s.supplier_pay(10,supplier,'100','To‘lov',method='transfer')
            sale=s.order(20,client,[dict(product=product,qty=2,price='125')],point=point,paid='50',payment='card')
            legacy=s.order(20,client,[dict(product=product,qty=1,price='125')],point=point,paid='0',payment='cash')
            s.db.execute("UPDATE sales SET currency='UZS' WHERE id=?",(legacy,))
            s.order(20,client,[dict(product=product,qty=1,price='125')],quote=True,payment='card',contact_phone='+998901234567',exchange_rate='12800')
            s.task(20,client,20,'2099-01-01 18:00','Mijozga qo‘ng‘iroq qilish')
            s.call(20,client,'Kelishildi','Ertaga bog‘lanish')
            s.delivery(20,client,sale,'Haydovchi','Toshkent','10','0')
            s.manager_record(10,20,'fund','20','Ish xarajatlari')
            s.manager_record(20,20,'expense','5','Yo‘l xarajati')
            import manager_money
            manager_money.request_return(s,20,dict(amount='10',note='Kassaga topshirish'))
            lot=s.db.execute('SELECT id FROM inventory_lots WHERE receipt=? LIMIT 1',(receipt,)).fetchone()[0]
            s.supplier_return(10,lot,1,'Bir dona qaytarish')
            cancelled=s.order(20,client,[dict(product=product,qty=1,price='125')],point=point,paid='0',payment='cash')
            s.cancel_sale(10,cancelled,'Mijoz qaytardi',refund_confirmed=True)
        server=MiniServer(('127.0.0.1',0),path,TOKEN);server.origin='http://localhost:'+str(server.server_address[1])
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']);errors=[]
                def context(lang,uid=10):
                    ctx=browser.new_context(viewport={'width':1440,'height':1000})
                    ctx.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.abort())
                    ctx.add_init_script('if(!localStorage.getItem("director-lang"))localStorage.setItem("director-lang",'+json.dumps(lang)+');')
                    if uid:
                        person={'id':uid,'first_name':'Direktor' if uid==10 else 'Menejer'}
                        ctx.add_init_script('window.Telegram={WebApp:{initData:'+json.dumps(signed(uid,query_id='localization-'+lang+'-'+str(uid),user=json.dumps(person)))+',ready(){},expand(){},BackButton:{show(){},hide(){},onClick(){}}}};')
                    page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)));return ctx,page
                raw_codes=re.compile(r'\b(active|cancelled|pending|draft|accepted|rejected|employee|director|retry_required|synced|sale_receipt|source_id|balance_after|receipt_qty|price_pending|stock_mode|price_mode)\b')
                for lang in ('uz','ru'):
                    ctx,page=context(lang);page.goto(server.origin+'/director')
                    try:expect(page.locator('.metric')).to_have_count(4)
                    except AssertionError:raise AssertionError({'errors':errors,'login':page.locator('#login-state').inner_text(),'status':page.locator('#status').inner_text()})
                    keys=page.locator('[data-section]').evaluate_all('(items)=>items.map(x=>x.dataset.section)')
                    for key in keys:
                        section(page,key);expect(page.locator('#content')).to_have_attribute('aria-busy','false')
                        text=page.locator('#workspace').inner_text()
                        assert not raw_codes.search(text),(lang,key,raw_codes.search(text).group())
                        assert not page.locator('#status').evaluate('(el)=>el.classList.contains("load-error")'),(lang,key,text)
                        if key=='quotes':
                            with page.expect_download() as download:page.locator('#content tr[data-id]').first.click()
                            target=Path(tmp)/('quote-'+lang+'.pdf');download.value.save_as(target)
                            assert target.read_bytes().startswith(b'%PDF-')
                        if key in ('sales','products','stock','receipts','payments','customer_returns','supplier_returns','expenses','clients','suppliers','staff','website'):
                            rows=page.locator('#content tr[data-id]')
                            if rows.count():
                                rows.first.click();expect(page.locator('#detail')).to_be_visible()
                                content=page.locator('#detail-content').inner_text()
                                assert not raw_codes.search(content),(lang,key,content)
                                assert ('Qo‘shimcha ma’lumot' if lang=='uz' else 'Дополнительные данные') not in content,(lang,key,content)
                                page.locator('#close-detail').click()
                    section(page,'sales');page.locator('#content tr[data-id]').filter(has_text='UZS').first.click()
                    page.locator('#detail-content button').filter(has_text='Qarz to‘lovi' if lang=='uz' else 'Оплата долга').click()
                    expect(page.locator('#detail-content h2')).to_contain_text('UZS')
                    expect(page.locator('input[name=amount]').locator('..')).to_contain_text('UZS')
                    page.locator('#close-detail').click()
                    section(page,'staff')
                    expect(page.locator('#content')).to_contain_text('Xodim' if lang=='uz' else 'Сотрудник')
                    if lang=='ru':page.screenshot(path=str(screens/'workspace-ru-staff.png'),full_page=False)
                    section(page,'overview');page.screenshot(path=str(screens/('workspace-'+lang+'-overview.png')),full_page=False)
                    if lang=='uz':
                        # A committed business write followed by failed refresh stays saved.
                        section(page,'clients');page.locator('#actions button').filter(has_text='Mijoz qo‘shish').click()
                        ctx.route('**/director-api/lookups',lambda r:r.fulfill(status=503,content_type='application/json',body=json.dumps({'error':'Sinov: aloqa uzildi'})))
                        page.locator('input[name=name]').fill('Yangi mijoz');page.locator('input[name=phone]').fill('+998901234568')
                        page.locator('#operation button[type=submit]').click();expect(page.locator('#detail')).not_to_be_visible()
                        expect(page.locator('#status')).to_contain_text('Saqlandi.')
                        assert s.db.execute("SELECT COUNT(*) FROM clients WHERE name='Yangi mijoz'").fetchone()[0]==1
                        ctx.unroute('**/director-api/lookups');page.locator('#actions button').filter(has_text='Ro‘yxatni yangilash').click()
                        expect(page.locator('#content')).to_contain_text('Yangi mijoz')
                        assert s.db.execute("SELECT COUNT(*) FROM clients WHERE name='Yangi mijoz'").fetchone()[0]==1
                    section(page,'overview');page.set_viewport_size({'width':390,'height':844})
                    menu(page);expect(page.locator('#sidebar')).to_have_css('transform','matrix(1, 0, 0, 1, 0, 0)')
                    page.screenshot(path=str(screens/('workspace-'+lang+'-menu.png')),full_page=False)
                    # A network failure must not pretend that server logout succeeded.
                    ctx.route('**/director-auth/logout',lambda r:r.fulfill(status=503,content_type='application/json',body=json.dumps({'error':'Server error'})))
                    page.locator('#logout').click();expect(page.locator('#workspace')).to_be_visible()
                    expect(page.locator('#session-error')).to_be_visible()
                    expect(page.locator('#session-error')).to_contain_text('Chiqib bo‘lmadi' if lang=='uz' else 'Не удалось выйти')
                    ctx.unroute('**/director-auth/logout');page.locator('#logout').click();expect(page.locator('#login')).to_be_visible()
                    expect(page.locator('#start-login')).to_have_text('Kirish kodini olish' if lang=='uz' else 'Получить код входа')
                    ctx.close()
                # Slow login polling never creates concurrent approval requests.
                ctx,login=context('ru',None);login.goto(server.origin+'/director');expect(login.locator('#login')).to_be_visible()
                login.set_viewport_size({'width':390,'height':844})
                login.locator('#header-language').click();expect(login.locator('#start-login')).to_have_text('Kirish kodini olish')
                login.locator('#header-language').click();expect(login.locator('#start-login')).to_have_text('Получить код входа')
                login.clock.install();pending=[];ctx.route('**/director-auth/poll',lambda r:pending.append(r))
                login.locator('#start-login').click();expect(login.locator('#login-code')).to_contain_text('/cabinet_login')
                with login.expect_request('**/director-auth/poll'):login.clock.run_for(8000)
                login.wait_for_function('loginPolling===true')
                assert len(pending)==1,len(pending)
                login.clock.run_for(8000);assert len(pending)==1,len(pending)
                pending.pop().fulfill(status=200,content_type='application/json',body='{"approved":false}')
                ctx.close()
                assert not errors,errors;browser.close()
            print(json.dumps({'result':'passed','checks':'17 sections and populated details in UZ/RU, translated status/role/action and fields, real UZS payment label, saved-write refresh failure once, failed logout stays signed in, successful logout, localized login, non-overlapping polling, mobile menus','screenshots':5}))
        finally:server.shutdown();server.server_close();thread.join();s.db.close()


if __name__=='__main__':main()
