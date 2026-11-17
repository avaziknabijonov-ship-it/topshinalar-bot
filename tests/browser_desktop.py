"""Optional real-Chromium check of the Windows desktop mode. Uses disposable fixtures, never production.
Run: python tests/browser_desktop.py   (playwright + Chromium required; CHROMIUM_PATH selects the binary)
The Electron window only adds "TopshinalarDesktop/<version>" to the User-Agent, so this drives
exactly what the installed app loads: Telegram-code login, wide layout, director cabinet, expiry.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store
from miniapp import MiniServer
import desktop_auth as desk
from test_miniapp import TOKEN

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36 TopshinalarDesktop/1.0.0'


def main():
    from playwright.sync_api import sync_playwright, expect
    root = Path(__file__).resolve().parents[1]
    screens = Path(os.environ.get('SCREENSHOT_DIR', Path(tempfile.gettempdir()) / 'desktop-screens'))
    screens.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'smoke.sqlite3'
        s = Store(path)
        s.configure([10], [20])
        with s.db:
            s.db.execute("UPDATE users SET name='Test direktor' WHERE id=10")
            s.db.execute("UPDATE users SET name='Test menejer' WHERE id=20")
            point = s.add('points', name='Test ombor')
            for i, name in enumerate(['Test shina 315/80 R22.5', 'Test shina 295/80 R22.5', 'Test shina 12.00 R20', 'Test shina 275/70 R22.5', 'Test shina 385/65 R22.5']):
                product = s.product(10, name, str(120 + i * 15) + '.00')
                s.move(20, product, point, 10 + i, 'in', 'fixture')
            s.client(20, 'Test mijoz', '+998900000001', '', '')
        server = MiniServer(('127.0.0.1', 0), path, TOKEN)
        port = server.server_address[1]
        server.origin = f'http://localhost:{port}'  # Chromium treats localhost as secure, so __Host- cookies work
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = server.origin
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'), args=['--no-sandbox'])

                def approve_from_page(page, uid):
                    expect(page.locator('#desktop-code')).to_contain_text('/desktop_login')
                    code = page.locator('#desktop-code').inner_text().split()[1]
                    desk.approve(s, uid, code)
                    s.db.commit()

                # 1) Mini App / ordinary browser: untouched behaviour, no desktop assets requested.
                plain = browser.new_context(viewport={'width': 390, 'height': 800})
                page = plain.new_page()
                requested = []
                page.on('request', lambda r: requested.append(r.url))
                page.goto(base + '/')
                expect(page.locator('#app')).to_contain_text('Telegram orqali oching')
                assert not [u for u in requested if u.endswith('/desktop.css')], requested
                assert page.evaluate('typeof window.DesktopSession') == 'undefined'
                assert not page.evaluate("document.documentElement.classList.contains('desktop-app')")
                plain.close()

                # 2) Employee in the desktop window.
                context = browser.new_context(viewport={'width': 1366, 'height': 768}, user_agent=UA)
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base + '/')
                expect(page.locator('.desktop-login')).to_be_visible()
                page.screenshot(path=str(screens / 'desktop-login-1366.png'))
                approve_from_page(page, 20)
                expect(page.locator('.product').first).to_be_visible(timeout=15000)
                expect(page.locator('#workspace-user')).to_contain_text('Test menejer')
                page.screenshot(path=str(screens / 'desktop-employee-catalog-1366x768.png'))
                for tab in ('clients', 'debts', 'dashboard', 'catalog'):
                    page.locator(f'#nav [data-tab="{tab}"]').click()
                    page.wait_for_timeout(500)
                    assert not page.locator('.error').count(), tab
                page.locator('#nav [data-tab="dashboard"]').click()
                page.wait_for_timeout(600)
                page.screenshot(path=str(screens / 'desktop-employee-work-1366x768.png'))
                # a real write through the cookie + CSRF path
                page.locator('#language').click()
                page.wait_for_timeout(700)
                assert s.db.execute('SELECT lang FROM users WHERE id=20').fetchone()[0] == 'ru'
                # 2b) page reload keeps the session (HttpOnly cookie, no second code)
                page.reload()
                expect(page.locator('.product').first).to_be_visible(timeout=15000)
                assert not page.locator('.desktop-login').count()
                # 2c) employee has no director cabinet
                page.goto(base + '/director')
                expect(page.locator('#login')).to_be_visible(timeout=10000)
                # 2d) wide screens
                page.goto(base + '/')
                expect(page.locator('.product').first).to_be_visible(timeout=15000)
                page.set_viewport_size({'width': 1920, 'height': 1080})
                page.wait_for_timeout(400)
                page.screenshot(path=str(screens / 'desktop-employee-catalog-1920x1080.png'))
                widths = page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
                assert widths <= 0, 'horizontal scroll at 1920'
                page.set_viewport_size({'width': 1024, 'height': 700})
                page.wait_for_timeout(400)
                assert page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth') <= 0, 'horizontal scroll at 1024'
                page.screenshot(path=str(screens / 'desktop-employee-catalog-1024x700.png'))
                # 2e) the session is revoked on the server -> next action returns to the Telegram code screen
                with s.db:
                    s.db.execute('DELETE FROM desktop_sessions')
                page.locator('#nav [data-tab="clients"]').click()
                expect(page.locator('.desktop-login')).to_be_visible(timeout=15000)
                context.close()

                # 3) Director: one code opens both the workspace and the cabinet.
                context = browser.new_context(viewport={'width': 1440, 'height': 900}, user_agent=UA)
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base + '/')
                approve_from_page(page, 10)
                expect(page.locator('#workspace-user')).to_contain_text('Test direktor', timeout=15000)
                page.goto(base + '/director')
                expect(page.locator('#workspace')).to_be_visible(timeout=15000)
                page.locator('.metric').first.wait_for(timeout=15000)
                page.screenshot(path=str(screens / 'desktop-director-1440x900.png'))
                context.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        assert not errors, errors
    print(json.dumps({'result': 'passed', 'screenshots': sorted(p.name for p in screens.glob('desktop-*.png')), 'dir': str(screens)}))


if __name__ == '__main__':
    main()
