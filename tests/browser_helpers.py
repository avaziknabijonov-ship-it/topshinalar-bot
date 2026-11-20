"""Use the visible cabinet navigation at either screen size."""
def menu(page):
    toggle=page.locator('#menu-toggle')
    if toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false':
        toggle.click()


def section(page, key):
    tab=None
    if key in ('customer_returns','supplier_returns'):
        # Both returns lists live under one menu entry with two tabs.
        tab=key;key='returns'
    menu(page)
    button=page.locator('[data-section="'+key+'"]')
    button.wait_for(state='attached')
    if not button.is_visible():
        # Menu groups are collapsible: open the group that holds this section.
        button.locator('xpath=ancestor::div[contains(@class,"nav-group")]//button[contains(@class,"nav-group-label")]').click()
    button.click()
    if tab:
        page.locator('[data-return-tab="'+tab+'"]').wait_for(state='visible')
        if page.locator('[data-return-tab="'+tab+'"].active').count()==0:
            page.locator('[data-return-tab="'+tab+'"]').click()


def filters(page):
    """Open the collapsible section filters if they are folded."""
    toggle=page.locator('#filter-toggle')
    if toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false':
        toggle.click()
