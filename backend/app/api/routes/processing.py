import json
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, status
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel, validator
from sqlmodel import Session
from app.api.deps import SessionDep, CurrentUser
from app.core.config import settings
from app.core.utils import get_supported_formats
from app.models import Job
from app.core.job_manager import manager as job_manager

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()


def _get_job(session: Session, job_id: str) -> Job | None:
    try:
        return session.get(Job, uuid.UUID(job_id))
    except ValueError:
        return None


class PdfCrop(BaseModel):
    x: float
    y: float
    width: float
    height: float


class PdfTransformation(BaseModel):
    rotate: int = 0
    crop: Optional[PdfCrop] = None

    @validator("rotate")
    def validate_rotate(cls, value):
        if value not in [0, 90, 180, 270]:
            raise ValueError("Rotation must be 0, 90, 180, or 270 degrees.")
        return value


class PdfPageRecipe(BaseModel):
    sourceFileId: str
    sourcePageIndex: int
    transformations: PdfTransformation


class PdfMergeRecipe(BaseModel):
    outputFilename: str
    pages: List[PdfPageRecipe]

    @validator("pages")
    def validate_pages(cls, value):
        if not value:
            raise ValueError("At least one PDF page is required.")
        return value


class ProcessOperationPayload(BaseModel):
    input: str
    output: Optional[str] = None
    type: str
    outputFormat: Optional[str] = None


# -------- Specific route (must come before the catch‑all) --------
@router.post('/pdf/merge', status_code=status.HTTP_200_OK)
def merge_pdf(
    current_user: CurrentUser,
    session: SessionDep,
    recipe: PdfMergeRecipe = Body(...),
):
    """Create a PDF Studio job from an uploaded-page recipe."""
    output_filename = Path(recipe.outputFilename.replace("\\", "/")).name or "merged_document.pdf"
    if not output_filename.lower().endswith(".pdf"):
        output_filename = f"{output_filename}.pdf"

    user_temp_dir = settings.TEMP_DIR / str(current_user.id)
    source_paths = {}
    normalized_pages = []
    for page in recipe.pages:
        try:
            source_id = str(uuid.UUID(page.sourceFileId))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid source file ID") from exc
        source_path = user_temp_dir / source_id
        if source_id not in source_paths:
            if not source_path.is_dir():
                raise HTTPException(status_code=404, detail="Uploaded PDF not found")
            pdf_files = [path for path in source_path.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"]
            if len(pdf_files) != 1:
                raise HTTPException(status_code=404, detail="Uploaded PDF not found")
            source_paths[source_id] = pdf_files[0]
        normalized_pages.append({
            **page.dict(),
            "sourceFileId": source_id,
        })

    job = Job(
        input_filename="__pdf_studio__",
        output_filename=output_filename,
        input_format="pdf",
        output_format="pdf",
        user_id=current_user.id,
        file_size=sum(path.stat().st_size for path in source_paths.values()),
        status="pending",
        progress=0,
    )
    job_dir = user_temp_dir / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = job_dir / "recipe.json"
    recipe_data = {
        "pages": normalized_pages,
        "source_paths": {key: str(path) for key, path in source_paths.items()},
    }
    try:
        recipe_path.write_text(json.dumps(recipe_data), encoding="utf-8")
    except OSError:
        logger.exception("Failed to persist PDF Studio recipe for job %s", job.id)
        raise HTTPException(status_code=500, detail="Could not prepare PDF job")

    session.add(job)
    session.commit()
    session.refresh(job)
    try:
        job_manager.enqueue(str(job.id))
    except RuntimeError as exc:
        job.status = "failed"
        job.error_message = "PDF processing service is unavailable"
        session.add(job)
        session.commit()
        logger.exception("Could not enqueue PDF Studio job %s", job.id)
        raise HTTPException(status_code=503, detail="PDF processing service is unavailable") from exc

    logger.info("PDF Studio job %s queued for user %s", job.id, current_user.id)
    return {
        "jobId": str(job.id),
        "status": job.status,
        "message": "PDF processing job queued.",
    }

@router.post('/upload')
def upload_file(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """Store one PDF for a user's PDF Studio workspace."""
    original_filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not original_filename or not original_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_id = str(uuid.uuid4())
    target = settings.TEMP_DIR / str(current_user.id) / file_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / original_filename
    written = 0
    try:
        with path.open("wb") as buffer:
            while chunk := file.file.read(64 * 1024):
                written += len(chunk)
                if written > settings.MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="File too large")
                buffer.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        target.rmdir()
        raise

    logger.info("PDF Studio upload %s stored for user %s", file_id, current_user.id)
    return {"fileId": file_id, "filename": original_filename, "size": written}


@router.get('/operations')
def get_operations(type: str):
    logger.info(f"Operations requested for type: {type}")
    formats = get_supported_formats()
    type = type.lower()
    if type not in formats:
        return []
    if type == 'pdf':
        return ['merge', 'split', 'compress']
    if type == 'image':
        return ['resize', 'compress', 'convert']
    return ['convert']


@router.get('/jobs/{job_id}')
def processing_job_status(
    job_id: str, 
    current_user: CurrentUser, 
    session: SessionDep
):
    logger.info(f"Status check for job {job_id} by user {current_user.id}")
    job = _get_job(session, job_id)
    if not job:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail='Job not found')
    if job.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail='Not authorized')
    return job


@router.get('/jobs/{job_id}/download')
def processing_job_download(
    job_id: str, 
    current_user: CurrentUser, 
    session: SessionDep
):
    logger.info(f"Download requested for job {job_id} by user {current_user.id}")
    job = _get_job(session, job_id)
    if not job:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail='Job not found')
    if job.user_id != current_user.id and not current_user.is_superuser:
        logger.warning(f"User {current_user.id} not authorized to download job {job_id}")
        raise HTTPException(status_code=403, detail='Not authorized')
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="PDF job is not complete")
    
    result_path = Path(settings.RESULTS_DIR) / str(job_id) / job.output_filename
    if not result_path.exists():
        logger.warning(f"Result file not found at {result_path}")
        raise HTTPException(status_code=404, detail='Result not found')
    
    logger.info(f"Serving file: {result_path}")
    return FileResponse(str(result_path), filename=result_path.name)