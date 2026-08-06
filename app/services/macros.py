from playwright.sync_api import Page

def locator_for(page: Page, selector_type: str, selector: str):
    if selector_type == "label":
        return page.get_by_label(selector)
    if selector_type == "text":
        return page.get_by_text(selector, exact=False)
    if selector_type == "role_button":
        return page.get_by_role("button", name=selector)
    if selector_type == "placeholder":
        return page.get_by_placeholder(selector)
    return page.locator(selector)

def execute_macro_actions(page: Page, actions):
    for action in actions:
        if not action.enabled:
            continue

        timeout = max(action.timeout_ms or 5000, 250)
        kind = action.action_type
        selector = action.selector or ""
        value = action.value or ""

        if kind == "wait":
            page.wait_for_timeout(int(float(value or "1") * 1000))
            continue

        if kind == "scroll":
            page.mouse.wheel(0, int(float(value or "800")))
            page.wait_for_timeout(300)
            continue

        if kind == "press":
            page.keyboard.press(value or "Enter")
            page.wait_for_timeout(300)
            continue

        loc = locator_for(page, action.selector_type, selector)

        if kind == "wait_for":
            loc.first.wait_for(state="visible", timeout=timeout)
        elif kind == "select":
            try:
                loc.first.select_option(label=value, timeout=timeout)
            except Exception:
                loc.first.select_option(value=value, timeout=timeout)
        elif kind == "fill":
            loc.first.fill(value, timeout=timeout)
        elif kind == "click":
            loc.first.click(timeout=timeout)
        elif kind == "check":
            should_check = value.strip().lower() not in ("0", "false", "off", "nein")
            if should_check:
                loc.first.check(timeout=timeout)
            else:
                loc.first.uncheck(timeout=timeout)

        page.wait_for_timeout(300)
