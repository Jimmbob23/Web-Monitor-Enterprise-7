from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.db import SessionLocal
from app.models import Site
from app.services.monitor import run_check

executors = {
    "default": ThreadPoolExecutor(max_workers=1),
}

job_defaults = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": 300,
}

scheduler = BackgroundScheduler(
    timezone=settings.app_timezone,
    executors=executors,
    job_defaults=job_defaults,
)

def check_job(site_id: int):
    db = SessionLocal()
    try:
        site = db.get(Site, site_id)
        if site and site.enabled:
            run_check(db, site_id)
    finally:
        db.close()

def trigger_for(site):
    if site.schedule_type == "cron" and site.cron_expression.strip():
        minute, hour, day, month, weekday = site.cron_expression.split()
        return CronTrigger(
            minute=minute, hour=hour, day=day, month=month,
            day_of_week=weekday, timezone=settings.app_timezone
        )
    return IntervalTrigger(seconds=max(site.interval_seconds, 60), timezone=settings.app_timezone)

def sync_jobs():
    db = SessionLocal()
    try:
        existing = {j.id for j in scheduler.get_jobs()}
        wanted = set()

        for site in db.query(Site).filter(Site.enabled == True).all():
            job_id = f"site-{site.id}"
            wanted.add(job_id)
            trigger = trigger_for(site)
            job = scheduler.get_job(job_id)
            if job:
                job.reschedule(trigger)
            else:
                scheduler.add_job(check_job, trigger, args=[site.id], id=job_id, replace_existing=True)

        for job_id in existing - wanted:
            if job_id.startswith("site-"):
                scheduler.remove_job(job_id)
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    sync_jobs()
