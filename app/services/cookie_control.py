import re

BUTTON_TEXTS = [
    "Alle akzeptieren","Alles akzeptieren","Akzeptieren","Zustimmen",
    "Accept all","Accept","Agree","I agree","OK","Okay"
]

SELECTORS = [
    "#onetrust-banner-sdk",".cookie-banner",".cookie-consent",".cookie-notice",
    ".cc-window",".cmpbox",".qc-cmp2-container",".fc-consent-root","#didomi-host"
]

def handle_cookies(page, mode: str):
    if mode in ("auto", "click"):
        for text in BUTTON_TEXTS:
            try:
                loc = page.get_by_role("button", name=re.compile(re.escape(text), re.I))
                if loc.count():
                    loc.first.click(timeout=1200)
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

    if mode in ("auto", "hide"):
        for sel in SELECTORS:
            try:
                page.locator(sel).evaluate_all("(els)=>els.forEach(e=>e.remove())")
            except Exception:
                pass
