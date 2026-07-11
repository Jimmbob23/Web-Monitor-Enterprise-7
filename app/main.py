from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import shutil
import tempfile

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import (
    create_session_token,
    current_user,
    ensure_admin_user,
    hash_password,
    require_login,
    verify_password,
)
from app.config import settings
from app.db import SessionLocal, get_db, init_db_with_retry
from app.models import BackupEntry, Change, Folder, MacroAction, Site, User
from app.services.backups import create_config_backup, restore_config_backup
from app.services.change_flags import clear_unread, has_unread
from app.services.monitor import normalize_url, run_check
from app.services.recorder import macro_recorder
from app.services.scheduler import scheduler, start_scheduler, sync_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_with_retry()
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()

    start_scheduler()
    yield

    try:
        macro_recorder.cancel_active()
    except Exception:
        pass

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Web Monitor Enterprise 7 Beta",
    version="7.0.0-beta",
    lifespan=lifespan,
)

app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def berlin_time(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except Exception:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(settings.app_timezone)).strftime("%d.%m.%Y %H:%M:%S")


templates.env.filters["berlin_time"] = berlin_time


def require_admin(request: Request, db: Session):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role != "admin":
        return RedirectResponse("/", status_code=303)
    return None


def delete_public_file(public_path: str):
    if not public_path or not public_path.startswith("/data/"):
        return
    try:
        path = (settings.data_dir / public_path.replace("/data/", "", 1)).resolve()
        if settings.data_dir.resolve() in path.parents and path.is_file():
            path.unlink(missing_ok=True)
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "version": "7.0.0-beta", "recorder": "novnc"}


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)):
    sites = db.query(Site).all()
    return {
        "sites": len(sites),
        "enabled": sum(1 for site in sites if site.enabled),
        "open_changes": sum(1 for site in sites if has_unread(site.id)),
        "errors": db.query(Change).filter(Change.status == "error").count(),
    }


@app.get("/api/sites")
def api_sites(db: Session = Depends(get_db)):
    return db.query(Site).order_by(Site.id.desc()).all()


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username, User.active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Ungültiger Login"},
            status_code=401,
        )

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session",
        create_session_token(username),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/")
def dashboard(
    request: Request,
    q: str = "",
    folder: str = "",
    status: str = "",
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    query = db.query(Site)

    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Site.name.ilike(like),
                Site.url.ilike(like),
                Site.tags_csv.ilike(like),
            )
        )

    if folder.strip():
        query = query.join(Folder, Site.folder_id == Folder.id).filter(Folder.name == folder)

    if status == "active":
        query = query.filter(Site.enabled == True)
    elif status == "paused":
        query = query.filter(Site.enabled == False)

    sites = query.order_by(Site.id.desc()).all()
    for site in sites:
        site.unread_change = has_unread(site.id)

    all_sites = db.query(Site).all()
    stats = {
        "sites": len(all_sites),
        "enabled": sum(1 for site in all_sites if site.enabled),
        "changed": sum(1 for site in all_sites if has_unread(site.id)),
        "errors": db.query(Change).filter(Change.status == "error").count(),
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "sites": sites,
            "folders": db.query(Folder).order_by(Folder.name).all(),
            "stats": stats,
            "q": q,
            "selected_folder": folder,
            "selected_status": status,
            "user": current_user(request, db),
        },
    )


@app.post("/sites")
def create_site(
    request: Request,
    name: str = Form(""),
    url: str = Form(...),
    folder_name: str = Form(""),
    tags_csv: str = Form(""),
    schedule_type: str = Form("interval"),
    interval_seconds: int = Form(300),
    cron_expression: str = Form(""),
    threshold_percent: float = Form(0.5),
    wait_seconds: int = Form(2),
    viewport_width: int = Form(1440),
    viewport_height: int = Form(1200),
    ignore_selectors: str = Form(""),
    cookie_mode: str = Form("auto"),
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    folder = None
    if folder_name.strip():
        folder = db.query(Folder).filter(Folder.name == folder_name.strip()).first()
        if not folder:
            folder = Folder(name=folder_name.strip())
            db.add(folder)
            db.flush()

    site = Site(
        name=name.strip() or normalize_url(url),
        url=normalize_url(url),
        folder_id=folder.id if folder else None,
        tags_csv=tags_csv.strip(),
        schedule_type=schedule_type,
        interval_seconds=max(interval_seconds, 60),
        cron_expression=cron_expression.strip(),
        threshold_percent=max(threshold_percent, 0),
        wait_seconds=max(wait_seconds, 0),
        viewport_width=max(viewport_width, 320),
        viewport_height=max(viewport_height, 320),
        ignore_selectors=ignore_selectors.strip(),
        cookie_mode=cookie_mode,
        enabled=True,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    sync_jobs()
    return RedirectResponse(f"/sites/{site.id}", status_code=303)


@app.get("/sites/{site_id}")
def site_detail(site_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        clear_unread(site_id)

    changes = (
        db.query(Change)
        .filter(Change.site_id == site_id)
        .order_by(Change.id.desc())
        .limit(250)
        .all()
    )

    return templates.TemplateResponse(
        "site.html",
        {
            "request": request,
            "site": site,
            "changes": changes,
            "recorder_status": macro_recorder.status(site_id),
        },
    )


@app.post("/sites/{site_id}/edit")
def edit_site(
    site_id: int,
    request: Request,
    name: str = Form(""),
    url: str = Form(...),
    folder_name: str = Form(""),
    tags_csv: str = Form(""),
    schedule_type: str = Form("interval"),
    interval_seconds: int = Form(300),
    cron_expression: str = Form(""),
    threshold_percent: float = Form(0.5),
    wait_seconds: int = Form(2),
    viewport_width: int = Form(1440),
    viewport_height: int = Form(1200),
    ignore_selectors: str = Form(""),
    cookie_mode: str = Form("auto"),
    enabled: str | None = Form(None),
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        folder = None
        if folder_name.strip():
            folder = db.query(Folder).filter(Folder.name == folder_name.strip()).first()
            if not folder:
                folder = Folder(name=folder_name.strip())
                db.add(folder)
                db.flush()

        site.name = name.strip() or normalize_url(url)
        site.url = normalize_url(url)
        site.folder_id = folder.id if folder else None
        site.tags_csv = tags_csv.strip()
        site.schedule_type = schedule_type
        site.interval_seconds = max(interval_seconds, 60)
        site.cron_expression = cron_expression.strip()
        site.threshold_percent = max(threshold_percent, 0)
        site.wait_seconds = max(wait_seconds, 0)
        site.viewport_width = max(viewport_width, 320)
        site.viewport_height = max(viewport_height, 320)
        site.ignore_selectors = ignore_selectors.strip()
        site.cookie_mode = cookie_mode
        site.enabled = enabled == "on"
        site.last_status = "enabled" if site.enabled else "paused"
        db.commit()

    sync_jobs()
    return RedirectResponse(f"/sites/{site_id}", status_code=303)


@app.post("/sites/{site_id}/toggle")
def toggle_site(site_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        site.enabled = not site.enabled
        site.last_status = "enabled" if site.enabled else "paused"
        db.commit()

    sync_jobs()
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@app.post("/sites/{site_id}/check")
def manual_check(site_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        run_check(db, site_id)

    return RedirectResponse(f"/sites/{site_id}", status_code=303)


@app.post("/sites/{site_id}/reset-baseline")
def reset_baseline(site_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        site.baseline_path = ""
        site.last_status = "baseline reset"
        site.last_error = ""
        db.commit()

    return RedirectResponse(f"/sites/{site_id}", status_code=303)


@app.post("/sites/{site_id}/delete")
def delete_site(site_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        for change in list(site.changes):
            delete_public_file(change.screenshot_path)
            delete_public_file(change.diff_path)
        db.delete(site)
        db.commit()

    clear_unread(site_id)
    sync_jobs()
    return RedirectResponse("/", status_code=303)


@app.post("/sites/{site_id}/macro-actions")
def add_macro_action(
    site_id: int,
    request: Request,
    action_type: str = Form(...),
    selector_type: str = Form("label"),
    selector: str = Form(""),
    value: str = Form(""),
    timeout_ms: int = Form(5000),
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    next_position = (
        db.query(MacroAction).filter(MacroAction.site_id == site_id).count() + 1
    )
    db.add(MacroAction(
        site_id=site_id,
        position=next_position,
        action_type=action_type,
        selector_type=selector_type,
        selector=selector.strip(),
        value=value.strip(),
        timeout_ms=max(timeout_ms, 250),
        enabled=True,
    ))
    db.commit()

    return RedirectResponse(f"/sites/{site_id}#macros", status_code=303)


@app.post("/macro-actions/{action_id}/delete")
def delete_macro_action(
    action_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    action = db.get(MacroAction, action_id)
    site_id = action.site_id if action else None

    if action:
        db.delete(action)
        db.commit()

    return RedirectResponse(
        f"/sites/{site_id}#macros" if site_id else "/",
        status_code=303,
    )


@app.post("/macro-actions/{action_id}/move")
def move_macro_action(
    action_id: int,
    request: Request,
    direction: str = Form(...),
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    action = db.get(MacroAction, action_id)
    if not action:
        return RedirectResponse("/", status_code=303)

    actions = (
        db.query(MacroAction)
        .filter(MacroAction.site_id == action.site_id)
        .order_by(MacroAction.position)
        .all()
    )

    index = actions.index(action)
    target = index - 1 if direction == "up" else index + 1

    if 0 <= target < len(actions):
        actions[index].position, actions[target].position = (
            actions[target].position,
            actions[index].position,
        )
        db.commit()

    return RedirectResponse(f"/sites/{action.site_id}#macros", status_code=303)


@app.post("/sites/{site_id}/recorder/start")
def start_macro_recorder(
    site_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if not site:
        return RedirectResponse("/", status_code=303)

    try:
        macro_recorder.start(site.id, normalize_url(site.url))
    except RuntimeError as exc:
        return RedirectResponse(
            f"/sites/{site_id}?recorder_error={str(exc)}#recorder",
            status_code=303,
        )

    return RedirectResponse(
        f"/sites/{site_id}?recorder_started=1#recorder",
        status_code=303,
    )


@app.get("/sites/{site_id}/recorder/status")
def macro_recorder_status(
    site_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return JSONResponse({"state": "unauthorized"}, status_code=401)
    return macro_recorder.status(site_id)


@app.post("/sites/{site_id}/recorder/stop")
def stop_macro_recorder(
    site_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    try:
        actions = macro_recorder.stop(site_id)
    except RuntimeError as exc:
        return RedirectResponse(
            f"/sites/{site_id}?recorder_error={str(exc)}#recorder",
            status_code=303,
        )

    if not actions:
        return RedirectResponse(
            f"/sites/{site_id}?recorder_error=Keine Schritte erkannt. "
            "Bitte nach dem Start warten, bis der Status recording anzeigt, "
            "und dann die Seite im noVNC-Fenster bedienen.#recorder",
            status_code=303,
        )

    db.query(MacroAction).filter(MacroAction.site_id == site_id).delete()

    for position, action in enumerate(actions, start=1):
        db.add(MacroAction(
            site_id=site_id,
            position=position,
            enabled=True,
            **action,
        ))

    db.commit()

    return RedirectResponse(
        f"/sites/{site_id}?recorder_saved={len(actions)}#macros",
        status_code=303,
    )


@app.post("/sites/{site_id}/recorder/cancel")
def cancel_macro_recorder(
    site_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    try:
        macro_recorder.cancel(site_id)
    except RuntimeError:
        pass

    return RedirectResponse(f"/sites/{site_id}#recorder", status_code=303)


@app.post("/changes/{change_id}/delete")
def delete_change(
    change_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    change = db.get(Change, change_id)
    site_id = change.site_id if change else None

    if change:
        delete_public_file(change.screenshot_path)
        delete_public_file(change.diff_path)
        db.delete(change)
        db.commit()

    return RedirectResponse(
        f"/sites/{site_id}" if site_id else "/",
        status_code=303,
    )


@app.post("/sites/{site_id}/history/delete")
def delete_history(
    site_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_login(request, db)
    if redirect:
        return redirect

    site = db.get(Site, site_id)
    if site:
        for change in list(site.changes):
            delete_public_file(change.screenshot_path)
            delete_public_file(change.diff_path)
            db.delete(change)

        site.baseline_path = ""
        site.last_status = "history cleared"
        site.last_error = ""
        db.commit()

    clear_unread(site_id)
    return RedirectResponse(f"/sites/{site_id}", status_code=303)


@app.get("/admin/users")
def users_page(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": db.query(User).order_by(User.id).all(),
        },
    )


@app.post("/admin/users")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    username = username.strip()
    if username and not db.query(User).filter(User.username == username).first():
        db.add(User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            active=True,
        ))
        db.commit()

    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    user = db.get(User, user_id)
    if user and user.username != settings.admin_user:
        user.active = not user.active
        db.commit()

    return RedirectResponse("/admin/users", status_code=303)


@app.get("/backups")
def backups_page(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "backups.html",
        {
            "request": request,
            "backups": db.query(BackupEntry).order_by(BackupEntry.id.desc()).all(),
            "message": "",
        },
    )


@app.post("/backups/create")
def backup_create(
    request: Request,
    file_format: str = Form("json"),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    create_config_backup(db, file_format=file_format)
    return RedirectResponse("/backups", status_code=303)


@app.get("/backups/{backup_id}/download")
def backup_download(
    backup_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    backup = db.get(BackupEntry, backup_id)
    if not backup:
        return RedirectResponse("/backups", status_code=303)

    media_type = (
        "text/csv; charset=utf-8"
        if backup.filename.lower().endswith(".csv")
        else "application/json"
    )

    return FileResponse(
        settings.backup_dir / backup.filename,
        filename=backup.filename,
        media_type=media_type,
    )


@app.post("/backups/restore")
async def backup_restore(
    request: Request,
    file: UploadFile = File(...),
    replace_existing: str | None = Form(None),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect

    original_suffix = Path(file.filename or "restore.json").suffix.lower()
    if original_suffix not in {".json", ".csv"}:
        original_suffix = ".json"

    with tempfile.NamedTemporaryFile(delete=False, suffix=original_suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        count = restore_config_backup(
            db,
            tmp_path,
            replace_existing=(replace_existing == "on"),
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    sync_jobs()

    return templates.TemplateResponse(
        "backups.html",
        {
            "request": request,
            "backups": db.query(BackupEntry).order_by(BackupEntry.id.desc()).all(),
            "message": f"{count} Monitor(e) inklusive Makros wiederhergestellt.",
        },
    )
