from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.core.config import settings
from app.core.database import engine, Base, init_db
from app.core.job_manager import manager as job_manager
from app.api.routes import auth as auth_router
from app.api.routes import users as users_router
from app.api.routes import uploads as uploads_router
from app.api.routes import jobs as jobs_router
from app.api.routes import processing as processing_router
from app.api.routes import conversions as conversions_router
import uvicorn
import logging
import sys

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

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="File conversion service with authentication",
    version="1.0.0",
    debug=settings.DEBUG,
)

# Add middleware (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG or settings.ENVIRONMENT == "development" else [str(o) for o in settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(auth_router.router, prefix=settings.API_V1_STR + "/auth", tags=["authentication"])
app.include_router(users_router.router, prefix=settings.API_V1_STR + "/users", tags=["users"])
app.include_router(uploads_router.router, prefix=settings.API_V1_STR + "/uploads", tags=["uploads"])
app.include_router(jobs_router.router, prefix=settings.API_V1_STR + "/jobs", tags=["jobs"])
app.include_router(conversions_router.router, prefix=settings.API_V1_STR + "/conversions", tags=["conversions"])
app.include_router(processing_router.router, prefix=settings.API_V1_STR + "/processing", tags=["processing"])

@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} API", "environment": settings.ENVIRONMENT}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "debug": settings.DEBUG}


@app.on_event("startup")
async def _startup():
    logger.info("Application starting up")
    # ensure DB tables exist and default user is created
    init_db()
    logger.info("Database initialized")
    # start async job workers
    await job_manager.start()
    logger.info(f"Job manager started with {job_manager.concurrency} workers")


@app.on_event("shutdown")
async def _shutdown():
    logger.info("Application shutting down")
    await job_manager.stop()
    logger.info("Job manager stopped")