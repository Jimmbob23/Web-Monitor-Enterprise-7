import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BackupEntry, Folder, MacroAction, Site
from app.services.monitor import normalize_url


CSV_FIELDS = [
    "name",
    "url",
    "folder",
    "tags_csv",
    "schedule_type",
    "interval_seconds",
    "cron_expression",
    "threshold_percent",
    "wait_seconds",
    "viewport_width",
    "viewport_height",
    "ignore_selectors",
    "cookie_mode",
    "enabled",
    "macro_actions_json",
]


def _site_to_dict(site: Site) -> dict[str, Any]:
    return {
        "name": site.name,
        "url": site.url,
        "folder": site.folder.name if site.folder else "",
        "tags_csv": site.tags_csv,
        "schedule_type": site.schedule_type,
        "interval_seconds": site.interval_seconds,
        "cron_expression": site.cron_expression,
        "threshold_percent": site.threshold_percent,
        "wait_seconds": site.wait_seconds,
        "viewport_width": site.viewport_width,
        "viewport_height": site.viewport_height,
        "ignore_selectors": site.ignore_selectors,
        "cookie_mode": site.cookie_mode,
        "enabled": site.enabled,
        "macro_actions": [
            {
                "position": action.position,
                "action_type": action.action_type,
                "selector_type": action.selector_type,
                "selector": action.selector,
                "value": action.value,
                "timeout_ms": action.timeout_ms,
                "enabled": action.enabled,
            }
            for action in site.macro_actions
        ],
    }


def create_config_backup(db: Session, file_format: str = "json") -> BackupEntry:
    file_format = file_format.lower().strip()
    if file_format not in {"json", "csv"}:
        file_format = "json"

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"enterprise6-macro-{stamp}.{file_format}"
    path = settings.backup_dir / filename
    sites = [_site_to_dict(site) for site in db.query(Site).order_by(Site.id).all()]

    if file_format == "csv":
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, delimiter=";")
            writer.writeheader()

            for site in sites:
                row = {
                    key: site.get(key, "")
                    for key in CSV_FIELDS
                    if key != "macro_actions_json"
                }
                row["enabled"] = "1" if site.get("enabled", True) else "0"
                row["macro_actions_json"] = json.dumps(
                    site.get("macro_actions", []),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                writer.writerow(row)
    else:
        path.write_text(
            json.dumps(
                {
                    "version": "6.1.4-macro-beta3",
                    "format": "json",
                    "sites": sites,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    entry = BackupEntry(filename=filename)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _bool_value(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if not text:
        return default

    return text not in {"0", "false", "off", "nein", "no"}


def _int_value(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")

    # Unterstützt sowohl Semikolon als auch Komma.
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"

    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)

        for raw in reader:
            macros_raw = (raw.get("macro_actions_json") or "").strip()
            macros: list[dict[str, Any]] = []

            if macros_raw:
                try:
                    parsed = json.loads(macros_raw)
                    if isinstance(parsed, list):
                        macros = [item for item in parsed if isinstance(item, dict)]
                except json.JSONDecodeError:
                    macros = []

            rows.append({
                "name": raw.get("name", ""),
                "url": raw.get("url", ""),
                "folder": raw.get("folder", ""),
                "tags_csv": raw.get("tags_csv", ""),
                "schedule_type": raw.get("schedule_type", "interval"),
                "interval_seconds": raw.get("interval_seconds", 300),
                "cron_expression": raw.get("cron_expression", ""),
                "threshold_percent": raw.get("threshold_percent", 0.5),
                "wait_seconds": raw.get("wait_seconds", 2),
                "viewport_width": raw.get("viewport_width", 1440),
                "viewport_height": raw.get("viewport_height", 1200),
                "ignore_selectors": raw.get("ignore_selectors", ""),
                "cookie_mode": raw.get("cookie_mode", "auto"),
                "enabled": raw.get("enabled", "1"),
                "macro_actions": macros,
            })

    return rows


def _read_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        rows = payload.get("sites", [])
        return [row for row in rows if isinstance(row, dict)]

    return []


def restore_config_backup(
    db: Session,
    backup_path: Path,
    replace_existing: bool = False,
) -> int:
    suffix = backup_path.suffix.lower()

    if suffix == ".csv":
        rows = _read_csv(backup_path)
    else:
        rows = _read_json(backup_path)

    if replace_existing:
        db.query(MacroAction).delete()
        db.query(Site).delete()
        db.commit()

    restored = 0

    for row in rows:
        url_raw = str(row.get("url", "")).strip()
        if not url_raw:
            continue

        url = normalize_url(url_raw)

        folder = None
        folder_name = str(row.get("folder", "")).strip()

        if folder_name:
            folder = db.query(Folder).filter(Folder.name == folder_name).first()

            if not folder:
                folder = Folder(name=folder_name)
                db.add(folder)
                db.flush()

        site = db.query(Site).filter(Site.url == url).first()

        if not site:
            site = Site(url=url)
            db.add(site)
            db.flush()

        site.name = str(row.get("name", "")).strip() or url
        site.folder_id = folder.id if folder else None
        site.tags_csv = str(row.get("tags_csv", "")).strip()
        site.schedule_type = str(row.get("schedule_type", "interval")).strip() or "interval"
        site.interval_seconds = max(_int_value(row.get("interval_seconds"), 300), 60)
        site.cron_expression = str(row.get("cron_expression", "")).strip()
        site.threshold_percent = max(_float_value(row.get("threshold_percent"), 0.5), 0)
        site.wait_seconds = max(_int_value(row.get("wait_seconds"), 2), 0)
        site.viewport_width = max(_int_value(row.get("viewport_width"), 1440), 320)
        site.viewport_height = max(_int_value(row.get("viewport_height"), 1200), 320)
        site.ignore_selectors = str(row.get("ignore_selectors", "")).strip()
        site.cookie_mode = str(row.get("cookie_mode", "auto")).strip() or "auto"
        site.enabled = _bool_value(row.get("enabled"), True)

        db.flush()

        db.query(MacroAction).filter(MacroAction.site_id == site.id).delete()

        macro_actions = row.get("macro_actions", [])
        if isinstance(macro_actions, list):
            for position, action in enumerate(macro_actions, start=1):
                if not isinstance(action, dict):
                    continue

                db.add(MacroAction(
                    site_id=site.id,
                    position=_int_value(action.get("position"), position),
                    action_type=str(action.get("action_type", "click")),
                    selector_type=str(action.get("selector_type", "css")),
                    selector=str(action.get("selector", "")),
                    value=str(action.get("value", "")),
                    timeout_ms=max(_int_value(action.get("timeout_ms"), 5000), 250),
                    enabled=_bool_value(action.get("enabled"), True),
                ))

        restored += 1

    db.commit()
    return restored
