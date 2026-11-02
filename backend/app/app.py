from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import init_db
from app.core.job_manager import manager as job_manager
from app.core.job_retention import clear_temporary_files, purge_expired_jobs
from app.api.routes import jobs as jobs_router
from app.api.routes import processing as processing_router
from app.api.routes import conversions as conversions_router
from app.api.routes import pipelines as pipelines_router
import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="Local file conversion service",
    version="1.0.0",
    debug=settings.DEBUG,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(jobs_router.router, prefix=settings.API_V1_STR + "/jobs", tags=["jobs"])
app.include_router(conversions_router.router, prefix=settings.API_V1_STR + "/conversions", tags=["conversions"])
app.include_router(processing_router.router, prefix=settings.API_V1_STR + "/processing", tags=["processing"])
app.include_router(pipelines_router.router, prefix=settings.API_V1_STR + "/processing/pipelines", tags=["pipelines"])

frontend_dir = Path(__file__).resolve().parent.parent / "static"

@app.get("/health")
async def health_check():
    return {"status": "healthy", "debug": settings.DEBUG}


@app.get("/", include_in_schema=False)
@app.get("/{file_path:path}", include_in_schema=False)
async def serve_frontend(file_path: str = ""):
    if file_path == "api" or file_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    index_path = frontend_dir / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run the development launcher to build it.",
        )

    requested_path = (frontend_dir / file_path).resolve()
    if frontend_dir.resolve() not in requested_path.parents and requested_path != frontend_dir.resolve():
        raise HTTPException(status_code=404, detail="Not found")
    if requested_path.is_file():
        media_type = "text/javascript" if requested_path.suffix.lower() == ".mjs" else None
        return FileResponse(requested_path, media_type=media_type)
    if Path(file_path).suffix:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(index_path)


@app.on_event("startup")
async def _startup():
    logger.info("Application starting up")
    init_db()
    logger.info("Database initialized")
    await asyncio.to_thread(clear_temporary_files)
    await asyncio.to_thread(purge_expired_jobs)
    await job_manager.start()
    logger.info(f"Job manager started with {job_manager.concurrency} workers")


@app.on_event("shutdown")
async def _shutdown():
    logger.info("Application shutting down")
    await job_manager.stop()
    logger.info("Job manager stopped")