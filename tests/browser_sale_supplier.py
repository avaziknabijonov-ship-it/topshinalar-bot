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
    screens = Path(os.environ.get('SCREENSHOT_DIR', Path(tempfile.gettempdir()) / 'supplier-screens'))
    screens.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'db'
        s = Store(path)
        s.configure([10], [20])
        with s.db:
            s.db.execute("UPDATE users SET name='Test menejer' WHERE id=20")
            s.set_contact_phone(20, '+998905550020')
            point = s.add('points', name='Test ombor')
            both = s.product(10, 'Test shina 315/80 R22.5', '125')
            single = s.product(10, 'Test shina 295/80 R22.5', '100')
            s.client(20, 'Test mijoz', '+998901234567', '', '')
            alpha = s.supplier_save(10, 'Alpha MChJ', '+998901111111', '')
            beta = s.supplier_save(10, 'Beta Trade', '+998902222222', '')
            today = now()[:10]
            s.receive(20, both, alpha, '90', [{'point': point, 'qty': 5}], 'A', today, 'USD')
            s.receive(20, both, beta, '95', [{'point': point, 'qty': 5}], 'B', today, 'USD')
            s.receive(20, single, alpha, '80', [{'point': point, 'qty': 5}], 'C', today, 'USD')
        server = MiniServer(('127.0.0.1', 0), path, TOKEN)
        server.origin = 'http://localhost:' + str(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'), args=['--no-sandbox'])
                ctx = browser.new_context(viewport={'width': 1366, 'height': 900})
                ctx.route('https://telegram.org/js/telegram-web-app.js', lambda r: r.abort())
                ctx.add_init_script('window.Telegram={WebApp:{initData:' + json.dumps(signed(20, query_id='supplier-browser')) + ',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{onClick(){},show(){},hide(){}}}};')
                page = ctx.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(server.origin + '/')
                expect(page.locator('.product').first).to_be_visible(timeout=15000)
                # product with two suppliers shows the split in its detail card
                page.locator('[data-detail]').first.click()
                expect(page.locator('#modal')).to_contain_text('Alpha MChJ: 5')
                expect(page.locator('#modal')).to_contain_text('Beta Trade: 5')
                page.locator('[data-close]').first.click()
                # add both products; open the sale form
                for pid in (both, single):
                    page.locator(f'[data-add="{pid}"]').first.click() if page.locator(f'[data-add="{pid}"]').count() else None
                if not page.locator('#nav [data-tab="cart"] .badge').count():
                    page.locator('[data-detail]').first.click()
                    page.locator('[data-add]').first.click()
                    page.locator('[data-close]').first.click()
                page.locator('#nav [data-tab="cart"]').click()
                page.locator('[data-action="checkout"]').click()
                expect(page.locator('#modal select[name="item_point_0"]')).to_be_visible()
                supplier_selects = page.locator('#modal select[name^="item_supplier_"]')
                n_items = page.locator('#modal select[name^="item_point_"]').count()
                # a selector appears only for products held by more than one supplier
                assert supplier_selects.count() == (1 if n_items == 2 else 1), (supplier_selects.count(), n_items)
                options = supplier_selects.first.locator('option').all_inner_texts()
                assert 'Avtomatik' in options[0] and any('Beta Trade' in o for o in options) and any('Alpha MChJ' in o for o in options), options
                page.screenshot(path=str(screens / 'sale-supplier-form.png'))
                page.locator('#modal select[name="client"]').select_option(index=1)
                page.locator('#modal select[name^="item_point_"]').first.select_option(str(point))
                for i in range(1, n_items):
                    page.locator(f'#modal select[name="item_point_{i}"]').select_option(str(point))
                supplier_selects.first.select_option(label=next(o for o in options if 'Beta Trade' in o))
                page.locator('#modal select[name="payment"]').select_option('naqd')
                page.locator('#modal form#operation button.primary').click()
                expect(page.locator('#modal')).to_contain_text('Beta Trade')
                page.screenshot(path=str(screens / 'sale-supplier-preview.png'))
                page.locator('[data-confirm]').click()
                page.wait_for_timeout(1500)
                row = s.db.execute("SELECT r.supplier,SUM(a.qty) q FROM sale_allocations a JOIN sale_items i ON i.id=a.item JOIN inventory_lots l ON l.id=a.lot JOIN receipts r ON r.id=l.receipt WHERE i.product=? GROUP BY r.supplier", (both,)).fetchall()
                assert [(r[0], r[1]) for r in row] == [(beta, 1)], [tuple(r) for r in row]
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
        assert not errors, errors
    print(json.dumps({'result': 'passed', 'dir': str(screens)}))


if __name__ == '__main__':
    main()
