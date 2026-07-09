"""
Automatisation navigateur via Playwright, même logique de whitelist
et de vérification panique que pour les actions desktop.
"""
from playwright.sync_api import sync_playwright
from backend.security.panic_button import check_abort
from backend.actions.desktop_actions import register_action

_playwright = None
_browser = None


def get_browser():
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
    return _browser


@register_action("fill_web_form")
def fill_web_form(url: str, fields: dict):
    check_abort()
    browser = get_browser()
    page = browser.new_page()
    page.goto(url)
    for selector, value in fields.items():
        check_abort()
        page.fill(selector, value)
    return page
