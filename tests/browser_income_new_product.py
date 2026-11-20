"""Real-Chromium check: Prixod (income) form has search inside the product field, a discount field, and no new-product buttons.
Run: python tests/browser_income_new_product.py  (CHROMIUM_PATH selects the browser)"""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store
from miniapp import MiniServer
from test_miniapp import signed, TOKEN


def main():
    from playwright.sync_api import sync_playwright, expect
    screens = Path(os.environ.get('SCREENSHOT_DIR', Path(tempfile.gettempdir()) / 'income-screens'))
    screens.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'db'
        s = Store(path)
        s.configure([10], [20])
        with s.db:
            s.add('points', name='Test ombor')
            s.product(10, 'Test shina 315/80 R22.5', '125')
        server = MiniServer(('127.0.0.1', 0), path, TOKEN)
        server.origin = 'http://localhost:' + str(server.server_address[1])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'), args=['--no-sandbox'])
                for name, viewport in (('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1366, 'height': 900})):
                    ctx = browser.new_context(viewport=viewport)
                    ctx.route('https://telegram.org/js/telegram-web-app.js', lambda r: r.abort())
                    ctx.add_init_script('window.Telegram={WebApp:{initData:' + json.dumps(signed(10, query_id='income-' + name)) + ',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{onClick(){},show(){},hide(){}}}};')
                    page = ctx.new_page()
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(server.origin + '/')
                    expect(page.locator('#nav')).to_be_visible(timeout=15000)
                    page.locator('#nav [data-tab="dashboard"]').click()
                    page.locator('[data-action="income"]').first.click()
                    modal = page.locator('#modal')
                    expect(modal.locator('select[name="product"]')).to_be_visible()
                    # The new-product button stays right under the product field; search lives inside the field.
                    assert modal.locator('[data-action="quick-product"]').count() == 1
                    order = modal.locator('#picker-product, select[name="product"], [data-action="quick-product"], select[name="supplier"], select[name="first_point"]').evaluate_all(
                        "els => els.map(e => e.tagName + ':' + (e.getAttribute('name') || e.id || e.dataset.action))")
                    assert order == ['INPUT:picker-product', 'SELECT:product', 'BUTTON:quick-product', 'SELECT:supplier', 'SELECT:first_point'], order
                    assert modal.locator('label:has(#picker-product):has(select[name="product"])').count() == 1
                    expect(modal.locator('input[name="discount"]')).to_be_visible()
                    assert modal.locator('[name="second_point"], [name="second_qty"]').count() == 0
                    page.screenshot(path=str(screens / f'income-form-{name}.png'))
                    ctx.close()
                browser.close()
        finally:
            server.shutdown()
    assert not errors, errors
    print(json.dumps({'result': 'passed'}))


if __name__ == '__main__':
    main()
