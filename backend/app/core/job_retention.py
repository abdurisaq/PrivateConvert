import logging
import shutil
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import Job, JobPreference

logger = logging.getLogger(__name__)

RETENTION_DAYS = {
    "normal": 30,
    "24h": 1,
    "7d": 7,
    "30d": 30,
    "60d": 60,
    "90d": 90,
    "forever": None,
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def delete_job_files(job: Job) -> None:
    for path in (
        settings.UPLOAD_DIR / str(job.id),
        settings.RESULTS_DIR / str(job.id),
        settings.TEMP_DIR / str(job.id),
    ):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def purge_expired_jobs(session: Session | None = None, now: datetime | None = None) -> int:
    owns_session = session is None
    session = session or Session(engine)
    now = now or datetime.utcnow()
    try:
        preference = session.get(JobPreference, 1)
        days = RETENTION_DAYS.get(preference.retention if preference else "normal", 30)
        if days is None:
            return 0

        cutoff = now - timedelta(days=days)
        jobs = session.exec(
            select(Job).where(Job.status.in_(TERMINAL_STATUSES))
        ).all()
        expired = []
        for job in jobs:
            created_at = job.created_at
            if created_at.tzinfo:
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            if created_at <= cutoff:
                expired.append(job)

        for job in expired:
            delete_job_files(job)
            session.delete(job)
        if expired:
            session.commit()
        return len(expired)
    except Exception:
        session.rollback()
        logger.exception("Could not purge expired jobs")
        raise
    finally:
        if owns_session:
            session.close()


def clear_temporary_files() -> None:
    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for path in settings.TEMP_DIR.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    with Session(engine) as session:
        interrupted = session.exec(
            select(Job).where(Job.status.in_(["pending", "processing"]))
        ).all()
        for job in interrupted:
            job.status = "failed"
            job.error_message = "Processing was interrupted by an application restart."
            job.completed_at = datetime.utcnow()
            session.add(job)
        if interrupted:
            session.commit()
        logger.info("Cleared temporary files and marked %s interrupted jobs", len(interrupted))
