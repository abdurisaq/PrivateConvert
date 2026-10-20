import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.job_manager import manager as job_manager
from app.models import Job
from app.schemas.job import JobCreate, JobRead, JobUpdate

router = APIRouter()


def _get_job(session: SessionDep, job_id: str) -> Job | None:
    try:
        return session.get(Job, uuid.UUID(job_id))
    except ValueError:
        return None


@router.post("/", response_model=JobRead)
def create_job(job_in: JobCreate, session: SessionDep):
    job = Job(**job_in.dict())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/")
def list_jobs(session: SessionDep, status: Optional[str] = None):
    statement = select(Job)
    if status:
        statement = statement.where(Job.status == status)
    return {"results": session.exec(statement).all()}


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/start", response_model=JobRead)
def start_job(job_id: str, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start job in {job.status} status",
        )

    job.status = "processing"
    session.add(job)
    session.commit()
    session.refresh(job)
    job_manager.enqueue(job_id)
    return job


@router.get("/{job_id}/download/")
def download_job_result(job_id: str, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    result_path = settings.RESULTS_DIR / str(job.id) / job.output_filename
    if not result_path.is_file():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(result_path, filename=job.output_filename)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job.status} status",
        )
    job.status = "cancelled"
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobRead)
def update_job(job_id: str, job_update: JobUpdate, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for key, value in job_update.dict(exclude_none=True).items():
        setattr(job, key, value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/{job_id}")
def delete_job(job_id: str, session: SessionDep):
    job = _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    for directory in (
        settings.UPLOAD_DIR / str(job.id),
        settings.RESULTS_DIR / str(job.id),
        settings.TEMP_DIR / str(job.id),
    ):
        if directory.exists():
            shutil.rmtree(directory)

    session.delete(job)
    session.commit()
    return {"status": "deleted"}
