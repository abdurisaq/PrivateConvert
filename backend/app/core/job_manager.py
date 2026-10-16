import asyncio
import os
import shutil
import logging
import uuid
import json
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from app.core.db import engine
from app.models import Job
from app.core.config import settings
from app.core.converters import get_converter

logger = logging.getLogger(__name__)


def _write_pdf_studio_output(recipe: dict, output_path):
    """Apply page order and transformations from a PDF Studio recipe."""
    from pypdf import PdfReader, PdfWriter

    readers = {}
    writer = PdfWriter()
    for page_recipe in recipe["pages"]:
        source_id = page_recipe["sourceFileId"]
        reader = readers.get(source_id)
        if reader is None:
            reader = PdfReader(recipe["source_paths"][source_id], strict=True)
            readers[source_id] = reader

        page_index = page_recipe["sourcePageIndex"]
        if page_index < 0 or page_index >= len(reader.pages):
            raise ValueError(f"Page {page_index + 1} does not exist in source PDF")
        writer.add_page(reader.pages[page_index])
        page = writer.pages[-1]
        transformations = page_recipe["transformations"]
        crop = transformations.get("crop")
        if crop is not None:
            left = crop["x"]
            bottom = crop["y"]
            right = left + crop["width"]
            top = bottom + crop["height"]
            media_box = page.mediabox
            if (
                left < float(media_box.left)
                or bottom < float(media_box.bottom)
                or right > float(media_box.right)
                or top > float(media_box.top)
                or left >= right
                or bottom >= top
            ):
                raise ValueError("Crop rectangle must be inside the page bounds")
            page.cropbox.lower_left = (left, bottom)
            page.cropbox.upper_right = (right, top)

        rotation = transformations["rotate"]
        if rotation:
            page.rotate(rotation)

    with output_path.open("wb") as output_file:
        writer.write(output_file)


class JobManager:
    def __init__(self, concurrency: Optional[int] = None):
        self.concurrency = concurrency or settings.MAX_CONCURRENT_PROCESSES
        self.queue: asyncio.Queue[str] = None  # Will be initialized on startup
        self.workers: list[asyncio.Task] = []
        self._running = False

    async def _worker(self, worker_id: int):
        logger.info(f"Worker {worker_id} started")
        while self._running:
            try:
                job_id = await self.queue.get()
                logger.info(f"Worker {worker_id} processing job {job_id}")
                try:
                    await self._process(job_id)
                except Exception as e:
                    logger.error(f"Worker {worker_id} error processing {job_id}: {str(e)}", exc_info=True)
                    # For now, we just mark as failed and continue
                    try:
                        with Session(engine) as session:
                            job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
                            job = session.get(Job, job_uuid)
                            if job:
                                job.status = "failed"
                                job.error_message = str(e)
                                session.add(job)
                                session.commit()
                    except Exception as db_error:
                        logger.error(f"Failed to update job status: {str(db_error)}")
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break

    async def _process(self, job_id: str):
        """Process a file conversion job."""
        try:
            # Convert job_id to UUID
            job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
            
            logger.info(f"Processing job {job_id}")
            # Update job status to processing
            is_pdf_studio_job = False
            with Session(engine) as s:
                job = s.get(Job, job_uuid)
                if not job:
                    logger.error(f"Job {job_id} not found in database")
                    return
                is_pdf_studio_job = job.input_filename == "__pdf_studio__"
                logger.info(f"Job {job_id} details: input_format={job.input_format}, output_format={job.output_format}, input_file={job.input_filename}")
                job.status = "processing"
                job.started_at = datetime.utcnow()
                s.add(job)
                s.commit()
                s.refresh(job)

            if is_pdf_studio_job:
                await self._process_pdf_studio(job_uuid, job)
                return

            # Get file paths
            upload_dir = os.path.join(str(settings.UPLOAD_DIR), str(job_id))
            result_dir = os.path.join(str(settings.RESULTS_DIR), str(job_id))
            os.makedirs(result_dir, exist_ok=True)
            
            input_path = os.path.join(upload_dir, job.input_filename)
            output_path = os.path.join(result_dir, job.output_filename)
            
            logger.info(f"Job {job_id} paths: input={input_path}, output={output_path}")

            # Verify input file exists
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            logger.info(f"Job {job_id} input file exists, size: {os.path.getsize(input_path)} bytes")

            # Get appropriate converter
            converter = get_converter(job.input_format, job.output_format)
            if not converter:
                raise ValueError(f"No converter available for {job.input_format} -> {job.output_format}")
            
            logger.info(f"Job {job_id} using converter: {converter.__name__}")

            # Execute conversion
            logger.info(f"Job {job_id} starting conversion")
            success = converter(input_path, output_path)
            logger.info(f"Job {job_id} conversion result: {success}")

            # Update job status
            with Session(engine) as s:
                job = s.get(Job, job_uuid)
                if not job:
                    logger.error(f"Job {job_id} disappeared during processing")
                    return
                
                # Check if job was cancelled during processing
                if job.status == "cancelled":
                    logger.info(f"Job {job_id} was cancelled during processing")
                    return

                if success and os.path.exists(output_path):
                    job.status = "completed"
                    job.progress = 100
                    job.completed_at = datetime.utcnow()
                    job.tool_used = converter.__name__.replace("convert_", "")
                    logger.info(f"Job {job_id} marked as completed")
                else:
                    job.status = "failed"
                    job.error_message = "Conversion failed: output file not created"
                    logger.error(f"Job {job_id} conversion failed: output file does not exist at {output_path}")
                
                s.add(job)
                s.commit()
                s.refresh(job)

        except Exception as e:
            logger.error(f"Job {job_id} processing error: {str(e)}", exc_info=True)
            # Mark job as failed
            try:
                job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
                with Session(engine) as s:
                    job = s.get(Job, job_uuid)
                    if job:
                        job.status = "failed"
                        job.error_message = str(e)
                        job.completed_at = datetime.utcnow()
                        s.add(job)
                        s.commit()
            except Exception as db_error:
                logger.error(f"Failed to mark job {job_id} as failed: {str(db_error)}")

    async def _process_pdf_studio(self, job_uuid: uuid.UUID, job: Job):
        """Apply a PDF Studio recipe and save its output in the standard results directory."""
        recipe_path = settings.TEMP_DIR / str(job.user_id) / str(job.id) / "recipe.json"
        with recipe_path.open(encoding="utf-8") as recipe_file:
            recipe = json.load(recipe_file)

        result_dir = settings.RESULTS_DIR / str(job.id)
        result_dir.mkdir(parents=True, exist_ok=True)
        output_path = result_dir / job.output_filename
        _write_pdf_studio_output(recipe, output_path)

        with Session(engine) as session:
            stored_job = session.get(Job, job_uuid)
            if stored_job is None:
                raise RuntimeError(f"PDF Studio job {job_uuid} disappeared during processing")
            if stored_job.status == "cancelled":
                output_path.unlink(missing_ok=True)
                return
            stored_job.status = "completed"
            stored_job.progress = 100
            stored_job.started_at = stored_job.started_at or datetime.utcnow()
            stored_job.completed_at = datetime.utcnow()
            stored_job.tool_used = "pdf_studio"
            session.add(stored_job)
            session.commit()

    async def start(self):
        if self._running:
            return
        self._running = True
        self.queue = asyncio.Queue()  # Initialize queue in async context
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker(i))
            self.workers.append(task)

    async def stop(self):
        self._running = False
        # wait for queue to drain
        await self.queue.join()
        for w in self.workers:
            w.cancel()

    def enqueue(self, job_id: str):
        """Enqueue a job for processing (can be called from sync context)."""
        if self.queue is None:
            logger.error(f"Job manager not started, cannot enqueue job {job_id}")
            raise RuntimeError("Job manager not started")
        logger.info(f"Enqueueing job {job_id}")
        self.queue.put_nowait(job_id)


# module level manager instance
manager = JobManager()
