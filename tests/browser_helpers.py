"""Use the visible cabinet navigation at either screen size."""
def menu(page):
    toggle=page.locator('#menu-toggle')
    if toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false':
        toggle.click()


def section(page, key):
    menu(page)
    button=page.locator('[data-section="'+key+'"]')
    button.wait_for(state='attached')
    if not button.is_visible():
        # Menu groups are collapsible: open the group that holds this section.
        button.locator('xpath=ancestor::div[contains(@class,"nav-group")]//button[contains(@class,"nav-group-label")]').click()
    button.click()


def filters(page):
    """Open the collapsible section filters if they are folded."""
    toggle=page.locator('#filter-toggle')
    if toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false':
        toggle.click()
