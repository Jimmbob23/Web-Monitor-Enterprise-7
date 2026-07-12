import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.services.cookie_control import handle_cookies
from app.services.macros import execute_macro_actions


def hide_custom(page, selectors: str):
    for selector in [item.strip() for item in selectors.split(",") if item.strip()]:
        try:
            page.locator(selector).evaluate_all(
                "(elements) => elements.forEach((element) => element.remove())"
            )
        except Exception:
            pass


def capture(site, output_path: Path, actions) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": site.viewport_width, "height": site.viewport_height},
            ignore_https_errors=True,
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        page = context.new_page()

        response = page.goto(
            site.url,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        status = response.status if response else 0

        page.wait_for_timeout(1200)
        handle_cookies(page, site.cookie_mode, site.ignore_selectors)

        execute_macro_actions(page, actions)

        page.wait_for_timeout(500)
        handle_cookies(page, site.cookie_mode, site.ignore_selectors)
        hide_custom(page, site.ignore_selectors)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        handle_cookies(page, site.cookie_mode, site.ignore_selectors)

        if site.wait_seconds:
            page.wait_for_timeout(site.wait_seconds * 1000)

        page.screenshot(path=str(output_path), full_page=True)
        browser.close()

    return status, int((time.perf_counter() - started) * 1000)
