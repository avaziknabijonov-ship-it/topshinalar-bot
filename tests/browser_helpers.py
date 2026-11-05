"""Use the visible cabinet navigation at either screen size."""
def menu(page):
    toggle=page.locator('#menu-toggle')
    if toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false':
        toggle.click()


def section(page, key):
    menu(page)
    page.locator('[data-section="'+key+'"]').click()
