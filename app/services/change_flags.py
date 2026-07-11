from pathlib import Path
from app.config import settings

def _path(site_id: int) -> Path:
    d = settings.data_dir / "unread_changes"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"site-{site_id}.flag"

def mark_unread(site_id: int):
    _path(site_id).write_text("1", encoding="utf-8")

def clear_unread(site_id: int):
    _path(site_id).unlink(missing_ok=True)

def has_unread(site_id: int) -> bool:
    return _path(site_id).exists()
