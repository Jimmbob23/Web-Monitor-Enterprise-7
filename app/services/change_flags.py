from pathlib import Path
from threading import RLock
from time import monotonic

from app.config import settings


_CACHE_TTL_SECONDS = 3.0
_cache: dict[int, tuple[float, bool]] = {}
_cache_lock = RLock()


def _path(site_id: int) -> Path:
    directory = settings.data_dir / "unread_changes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"site-{site_id}.flag"


def mark_unread(site_id: int):
    _path(site_id).write_text("1", encoding="utf-8")
    with _cache_lock:
        _cache[site_id] = (monotonic(), True)


def clear_unread(site_id: int):
    _path(site_id).unlink(missing_ok=True)
    with _cache_lock:
        _cache[site_id] = (monotonic(), False)


def has_unread(site_id: int) -> bool:
    now = monotonic()

    with _cache_lock:
        cached = _cache.get(site_id)
        if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
            return cached[1]

    value = _path(site_id).exists()

    with _cache_lock:
        _cache[site_id] = (now, value)

    return value


def invalidate_unread_cache(site_id: int | None = None):
    with _cache_lock:
        if site_id is None:
            _cache.clear()
        else:
            _cache.pop(site_id, None)
