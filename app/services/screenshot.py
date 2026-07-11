import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.services.cookie_control import handle_cookies
from app.services.macros import execute_macro_actions

def hide_custom(page, selectors: str):
    for selector in [x.strip() for x in selectors.split(",") if x.strip()]:
        try:
            page.locator(selector).evaluate_all("(els)=>els.forEach(e=>e.remove())")
        except Exception:
            pass

def capture(site, output_path: Path, actions) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": site.viewport_width, "height": site.viewport_height},
            ignore_https_errors=True,
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        page = context.new_page()
        response = page.goto(site.url, wait_until="domcontentloaded", timeout=60000)
        status = response.status if response else 0

        page.wait_for_timeout(1000)
        handle_cookies(page, site.cookie_mode)
        execute_macro_actions(page, actions)
        handle_cookies(page, site.cookie_mode)
        hide_custom(page, site.ignore_selectors)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        if site.wait_seconds:
            page.wait_for_timeout(site.wait_seconds * 1000)

        page.screenshot(path=str(output_path), full_page=True)
        browser.close()

    return status, int((time.perf_counter() - start) * 1000)
