import re
from playwright.sync_api import Page


REJECT_TEXTS = [
    "Alle ablehnen",
    "Alles ablehnen",
    "Ablehnen",
    "Nur notwendige",
    "Nur notwendige Cookies",
    "Nur erforderliche Cookies",
    "Notwendige Cookies",
    "Essenzielle Cookies",
    "Erforderliche Cookies",
    "Reject all",
    "Reject",
    "Decline",
    "Only necessary",
    "Necessary only",
]

ACCEPT_TEXTS = [
    "Alle akzeptieren",
    "Alles akzeptieren",
    "Akzeptieren",
    "Zustimmen",
    "Einverstanden",
    "Accept all",
    "Accept",
    "Agree",
    "I agree",
    "Allow all",
]

SAVE_TEXTS = [
    "Auswahl speichern",
    "Einstellungen speichern",
    "Speichern",
    "Save selection",
    "Save preferences",
    "Confirm choices",
]

REJECT_SELECTORS = [
    "#onetrust-reject-all-handler",
    "#CybotCookiebotDialogBodyButtonDecline",
    "button[data-testid='uc-deny-all-button']",
    "button[data-testid='uc-reject-all-button']",
    "#didomi-notice-disagree-button",
    ".qc-cmp2-summary-buttons button[mode='secondary']",
    "button.sp_choice_type_REJECT_ALL",
    ".cmpboxbtnno",
    ".cmplz-deny",
]

ACCEPT_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "button[data-testid='uc-accept-all-button']",
    "#didomi-notice-agree-button",
    ".qc-cmp2-summary-buttons button[mode='primary']",
    "button.sp_choice_type_ACCEPT_ALL",
    ".cmpboxbtnyes",
    ".cmplz-accept",
]

BANNER_SELECTORS = [
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk",
    "#CybotCookiebotDialog",
    "#CybotCookiebotDialogBodyUnderlay",
    "#usercentrics-root",
    "[data-testid='uc-container']",
    "#didomi-host",
    ".didomi-popup-container",
    ".qc-cmp2-container",
    ".qc-cmp2-persistent-link",
    ".sp_message_container",
    ".sp_veil",
    ".cmpbox",
    ".cmpboxrecall",
    ".cmplz-cookiebanner",
    ".borlabs-cookie",
    "#BorlabsCookieBox",
    ".iubenda-cs-container",
    ".iubenda-cs-overlay",
    ".cookie-banner",
    ".cookie-consent",
    ".cookie-notice",
    ".cookie-overlay",
    ".consent-overlay",
    ".privacy-modal",
    "[class*='cookie-banner']",
    "[class*='cookie_banner']",
    "[class*='cookie-consent']",
    "[class*='cookie_consent']",
    "[class*='consent-banner']",
    "[class*='consent_modal']",
    "[id*='cookie-banner']",
    "[id*='cookie_banner']",
    "[id*='cookie-consent']",
    "[id*='consent-banner']",
]


def _frames(page: Page):
    return [page.main_frame] + [
        frame for frame in page.frames
        if frame is not page.main_frame
    ]


def _click_selector(frame, selector: str, timeout: int = 1600) -> bool:
    try:
        locator = frame.locator(selector).first
        if locator.count() and locator.is_visible():
            locator.click(timeout=timeout)
            return True
    except Exception:
        pass
    return False


def _click_text(frame, texts: list[str], timeout: int = 1600) -> bool:
    for text in texts:
        pattern = re.compile(rf"^\s*{re.escape(text)}\s*$", re.I)

        for locator in (
            frame.get_by_role("button", name=pattern).first,
            frame.get_by_role("link", name=pattern).first,
            frame.get_by_text(pattern, exact=False).first,
        ):
            try:
                if locator.count() and locator.is_visible():
                    locator.click(timeout=timeout)
                    return True
            except Exception:
                pass

    return False


def _remove_elements(page: Page, extra_selectors: str = "") -> None:
    selectors = list(BANNER_SELECTORS)
    selectors.extend(
        selector.strip()
        for selector in (extra_selectors or "").split(",")
        if selector.strip()
    )

    script = (
        "(selectors) => {"
        "for (const selector of selectors) {"
        "try { document.querySelectorAll(selector).forEach(e => e.remove()); } catch (_) {}"
        "}"
        "document.documentElement.style.setProperty('overflow','auto','important');"
        "document.documentElement.style.setProperty('position','static','important');"
        "document.body.style.setProperty('overflow','auto','important');"
        "document.body.style.setProperty('position','static','important');"
        "document.body.style.setProperty('padding-right','0','important');"
        "document.body.classList.remove("
        "'modal-open','no-scroll','noscroll','overflow-hidden','cookie-modal-open'"
        ");"
        "}"
    )

    for frame in _frames(page):
        try:
            frame.evaluate(script, selectors)
        except Exception:
            pass


def _remove_large_overlays(page: Page) -> None:
    script = (
        "() => {"
        "document.querySelectorAll('body *').forEach(e => {"
        "const s = getComputedStyle(e);"
        "const z = parseInt(s.zIndex || '0', 10);"
        "if (s.position === 'fixed' && z >= 100 && "
        "e.offsetWidth >= innerWidth * 0.7 && "
        "e.offsetHeight >= innerHeight * 0.7) { e.remove(); }"
        "});"
        "}"
    )

    for frame in _frames(page):
        try:
            frame.evaluate(script)
        except Exception:
            pass


def handle_cookies(page: Page, mode: str, extra_selectors: str = "") -> None:
    normalized = (mode or "necessary").strip().lower()
    normalized = {
        "auto": "necessary",
        "click": "accept",
    }.get(normalized, normalized)

    if normalized == "off":
        return

    page.wait_for_timeout(700)

    if normalized in {"necessary", "strict"}:
        clicked = False

        for frame in _frames(page):
            for selector in REJECT_SELECTORS:
                if _click_selector(frame, selector):
                    clicked = True
                    break

            if clicked or _click_text(frame, REJECT_TEXTS):
                break

        if clicked:
            page.wait_for_timeout(350)

            for frame in _frames(page):
                if _click_text(frame, SAVE_TEXTS):
                    break

    elif normalized == "accept":
        clicked = False

        for frame in _frames(page):
            for selector in ACCEPT_SELECTORS:
                if _click_selector(frame, selector):
                    clicked = True
                    break

            if clicked or _click_text(frame, ACCEPT_TEXTS):
                break

    if normalized in {"necessary", "accept", "hide", "strict"}:
        _remove_elements(page, extra_selectors)

    if normalized == "strict":
        _remove_large_overlays(page)
        page.wait_for_timeout(300)
        _remove_elements(page, extra_selectors)
