from datetime import datetime
from pathlib import Path
from threading import Lock
from app.config import settings
from app.models import Change, Site
from app.services.change_flags import mark_unread
from app.services.compare import compare_images
from app.services.screenshot import capture


_global_check_lock = Lock()

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def public_path(path: Path) -> str:
    return str(path).replace(str(settings.data_dir), "/data")

def _run_check_unlocked(db, site_id: int):
    site = db.get(Site, site_id)
    if not site:
        raise ValueError("Monitor nicht gefunden")

    site.url = normalize_url(site.url)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    shot = settings.screenshot_dir / f"site-{site.id}" / f"{stamp}.png"
    diff = settings.diff_dir / f"site-{site.id}" / f"{stamp}.png"
    change = Change(site_id=site.id, checked_at=datetime.utcnow())

    try:
        status, duration = capture(site, shot, site.macro_actions)
        change.http_status = status
        change.duration_ms = duration
        change.screenshot_path = public_path(shot)
        site.last_http_status = status
        site.last_duration_ms = duration

        if not site.baseline_path:
            site.baseline_path = str(shot)
            site.last_status = "baseline"
            change.status = "baseline"
        else:
            changed, percent = compare_images(Path(site.baseline_path), shot, diff)
            change.difference_percent = percent

            if changed and percent >= site.threshold_percent:
                change.changed = True
                change.status = "changed"
                change.diff_path = public_path(diff)
                site.baseline_path = str(shot)
                site.last_status = "changed"
                mark_unread(site.id)
            else:
                change.status = "unchanged"
                if site.last_status != "changed":
                    site.last_status = "unchanged"

        site.last_error = ""

    except Exception as exc:
        change.status = "error"
        change.error = str(exc)
        site.last_status = "error"
        site.last_error = str(exc)
        mark_unread(site.id)

    site.last_checked_at = datetime.utcnow()
    db.add(change)
    db.commit()
    db.refresh(change)
    return change


def run_check(db, site_id: int):
    """
    Serialisiert alle Prüfungen innerhalb des Containers.

    Scheduler, manuelle Prüfung und Makro-Test können dadurch nicht
    gleichzeitig Chromium/Playwright starten.
    """
    with _global_check_lock:
        return _run_check_unlocked(db, site_id)

