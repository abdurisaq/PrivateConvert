import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.job_manager import manager as job_manager
from app.core.pipeline_catalog import OPERATIONS, VIDEO_FORMATS
from app.core.pipeline_engine import PipelineError, output_extension, validate_pipeline
from app.models import Job, SavedPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/operations")
def list_pipeline_operations():
    return {
        "operations": {
            name: {
                **operation,
                "available": all(shutil.which(tool) for tool in operation.get("requires", [])),
            }
            for name, operation in OPERATIONS.items()
        }
    }


def _probe_video(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise HTTPException(status_code=503, detail="Video metadata requires ffprobe on the server")
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,width,height,bit_rate",
                "-of", "json", "-protocol_whitelist", "file,pipe", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        media = json.loads(result.stdout)
        streams = media.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
        return {
            "duration": float(media["format"]["duration"]),
            "width": video.get("width"),
            "height": video.get("height"),
            "audio_bitrate": int(audio["bit_rate"]) if audio.get("bit_rate") else None,
            "has_audio": bool(audio),
        }
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not inspect video metadata: {exc}") from exc


@router.post("/video-info")
async def get_video_info(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {f".{fmt}" for fmt in VIDEO_FORMATS}:
        raise HTTPException(status_code=415, detail="Unsupported video format")

    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=settings.TEMP_DIR, suffix=suffix, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        size = 0
        with temporary_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="Video exceeds the file size limit")
                output.write(chunk)
        return await asyncio.to_thread(_probe_video, temporary_path)
    finally:
        temporary_path.unlink(missing_ok=True)
        await file.close()


@router.post("/validate")
def validate_saved_pipeline(definition: dict = Body(...)):
    try:
        return {"pipeline": validate_pipeline(definition)}
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def list_saved_pipelines(session: SessionDep):
    pipelines = session.exec(select(SavedPipeline).order_by(SavedPipeline.name)).all()
    return {
        "results": [
            {"id": str(pipeline.id), **json.loads(pipeline.definition)}
            for pipeline in pipelines
        ]
    }


@router.post("")
def save_pipeline(session: SessionDep, definition: dict = Body(...)):
    try:
        clean_definition = validate_pipeline(definition)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name = clean_definition["name"]
    if not name or name == "Untitled pipeline":
        raise HTTPException(status_code=422, detail="Give the pipeline a name before saving")

    pipeline = session.exec(
        select(SavedPipeline).where(SavedPipeline.name == name)
    ).first()
    if pipeline is None:
        pipeline = SavedPipeline(name=name, definition=json.dumps(clean_definition))
    else:
        pipeline.definition = json.dumps(clean_definition)
        pipeline.updated_at = datetime.utcnow()
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return {"id": str(pipeline.id), **clean_definition}


@router.delete("/{pipeline_id}")
def delete_pipeline(pipeline_id: str, session: SessionDep):
    try:
        parsed_id = uuid.UUID(pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Pipeline not found") from exc
    pipeline = session.get(SavedPipeline, parsed_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    session.delete(pipeline)
    session.commit()
    return {"status": "deleted"}


@router.post("/run")
def run_saved_pipeline(
    session: SessionDep,
    files: list[UploadFile] = File(...),
    pipeline: str = Form(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one file")
    try:
        definition = validate_pipeline(json.loads(pipeline))
    except (json.JSONDecodeError, PipelineError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid pipeline: {exc}") from exc

    staged: list[tuple[Job, Path, Path]] = []
    total_size = 0
    database_committed = False
    try:
        for uploaded_file in files:
            filename = Path((uploaded_file.filename or "").replace("\\", "/")).name
            if not filename or filename in {".", ".."}:
                raise HTTPException(status_code=400, detail="Invalid filename")
            try:
                validate_pipeline(definition, Path(filename))
            except PipelineError as exc:
                raise HTTPException(status_code=422, detail=f"{filename}: {exc}") from exc

            extension = output_extension(definition, filename)
            job = Job(
                input_filename=filename,
                output_filename=f"{Path(filename).stem}.processed{extension}",
                input_format=Path(filename).suffix.lstrip(".").lower(),
                output_format=extension.lstrip("."),
                status="pending",
                tool_used="pipeline",
            )
            upload_dir = settings.UPLOAD_DIR / str(job.id)
            recipe_dir = settings.TEMP_DIR / str(job.id)
            upload_dir.mkdir(parents=True, exist_ok=True)
            recipe_dir.mkdir(parents=True, exist_ok=True)
            source_path = upload_dir / filename
            size = 0
            try:
                with source_path.open("wb") as output:
                    while chunk := uploaded_file.file.read(64 * 1024):
                        size += len(chunk)
                        total_size += len(chunk)
                        if size > settings.MAX_FILE_SIZE or total_size > settings.MAX_FILE_SIZE:
                            raise HTTPException(
                                status_code=413,
                                detail="Pipeline upload exceeds the file size limit",
                            )
                        output.write(chunk)
                (recipe_dir / "pipeline.json").write_text(
                    json.dumps(definition), encoding="utf-8"
                )
            except Exception:
                shutil.rmtree(upload_dir, ignore_errors=True)
                shutil.rmtree(recipe_dir, ignore_errors=True)
                raise
            job.file_size = size
            staged.append((job, upload_dir, recipe_dir))

        for job, _, _ in staged:
            session.add(job)
        session.commit()
        database_committed = True

        queued = []
        for job, _, _ in staged:
            try:
                job_manager.enqueue(str(job.id))
            except RuntimeError:
                job.status = "failed"
                job.error_message = "Processing service is unavailable"
                job.completed_at = datetime.utcnow()
                session.add(job)
                session.commit()
                logger.exception("Could not enqueue pipeline job %s", job.id)
            queued.append({"jobId": str(job.id), "filename": job.input_filename})
        return {"jobs": queued}
    except Exception:
        session.rollback()
        if not database_committed:
            for _, upload_dir, recipe_dir in staged:
                shutil.rmtree(upload_dir, ignore_errors=True)
                shutil.rmtree(recipe_dir, ignore_errors=True)
        raise
