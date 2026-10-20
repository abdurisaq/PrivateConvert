from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.core.utils import get_supported_formats
from app.core.config import settings
from app.api.deps import SessionDep
from app.models import Job
from app.core.job_manager import manager as job_manager
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/formats/')
def get_formats():
    """Get all supported conversion formats."""
    return get_supported_formats()


@router.post('/upload/')
def upload_conversion(
    session: SessionDep,
    file: UploadFile = File(...),
    input_format: str = Form(...),
    output_format: str = Form(...),
):
    """Upload a file for conversion."""
    filename = Path(file.filename or "").name
    if not filename or not input_format or not output_format:
        raise HTTPException(status_code=400, detail='Missing required fields')

    size = 0
    job = Job(
        input_filename=filename,
        output_filename=f"{Path(filename).stem}.{output_format.lower()}",
        input_format=input_format.lower(),
        output_format=output_format.lower(),
        status='pending',
        progress=0
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    upload_dir = Path(settings.UPLOAD_DIR) / str(job.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename
    
    try:
        with open(dest, 'wb') as buffer:
            for chunk in iter(lambda: file.file.read(1024*64), b''):
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE:
                    if dest.exists():
                        dest.unlink()
                    session.delete(job)
                    session.commit()
                    raise HTTPException(status_code=413, detail='File too large')
                buffer.write(chunk)

        job.file_size = size
        session.add(job)
        session.commit()

        logger.info(f"Job {job.id} created, enqueueing for processing")
        job_manager.enqueue(str(job.id))
        logger.info(f"Job {job.id} enqueued successfully")

        return {"data": {"jobId": str(job.id)}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        if dest.exists():
            dest.unlink()
        session.delete(job)
        session.commit()
        raise HTTPException(status_code=500, detail=str(e))
