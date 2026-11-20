"""Real-Chromium check of choosing a supplier in the sale form; disposable fixtures only.
Run: python tests/browser_sale_supplier.py  (CHROMIUM_PATH selects the browser)"""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store, now
from miniapp import MiniServer
from test_miniapp import signed, TOKEN


def main():
    from playwright.sync_api import sync_playwright, expect
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'db'
        s = Store(path)
        s.configure([10], [20])
        with s.db:
            s.db.execute("UPDATE users SET name='Test menejer' WHERE id=20")
            s.set_contact_phone(20, '+998905550020')
            point = s.add('points', name='Test ombor')
            product = s.product(10, 'Test shina 315/80 R22.5', '125')
            s.db.execute('UPDATE products SET wholesale_price=10000 WHERE id=?', (product,))
            retail = s.client(20, 'A chakana mijoz', '+998901234567', '', '')
            wholesale = s.client(20, 'B optom mijoz', '+998901234568', '', '')
            s.db.execute("UPDATE clients SET category='wholesale' WHERE id=?", (wholesale,))
            s.move(20, product, point, 5, 'in', '')
        server = MiniServer(('127.0.0.1', 0), path, TOKEN)
        server.origin = 'http://localhost:' + str(server.server_address[1])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'), args=['--no-sandbox'])
                ctx = browser.new_context(viewport={'width': 1366, 'height': 900})
                ctx.route('https://telegram.org/js/telegram-web-app.js', lambda r: r.abort())
                ctx.add_init_script('window.Telegram={WebApp:{initData:' + json.dumps(signed(20, query_id='price-type-browser')) + ',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{onClick(){},show(){},hide(){}}}};')
                page = ctx.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(server.origin + '/')
                expect(page.locator('.product').first).to_be_visible(timeout=15000)
                page.locator(f'[data-add="{product}"]').first.click()
                page.locator('#nav [data-tab="cart"]').click()
                page.locator('[data-action="checkout"]').click()
                modal = page.locator('#modal')
                for client, expected, other in ((wholesale, '100.00 USD', '125.00 USD'), (retail, '125.00 USD', '100.00 USD')):
                    modal.locator('select[name="client"]').select_option(str(client))
                    modal.locator('select[name^="item_point_"]').first.select_option(str(point))
                    modal.locator('select[name="payment"]').select_option('naqd')
                    modal.locator('form#operation button.primary').click()
                    expect(modal).to_contain_text(expected)
                    assert other not in modal.inner_text(), modal.inner_text()
                    modal.locator('[data-edit-form]').click()
                browser.close()
        finally:
            server.shutdown()
    assert not errors, errors
    print(json.dumps({'result': 'passed', 'checks': 'wholesale client gets wholesale price, retail client gets retail price, switching back restores'}))


if __name__ == '__main__':
    main()
