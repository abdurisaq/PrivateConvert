import asyncio
import io
import json
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_db
from app.api.routes import pipelines
from app.core import job_manager as job_manager_module
from app.core.config import settings
from app.core.job_manager import JobManager
from app.models import Job


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_pipeline_save_and_multi_file_queue(tmp_path, monkeypatch):
    engine = _database()
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "TEMP_DIR", tmp_path / "temp")
    queued = []
    monkeypatch.setattr(pipelines.job_manager, "enqueue", queued.append)

    def database_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(pipelines.router, prefix="/pipelines")
    app.dependency_overrides[get_db] = database_session

    pipeline = {
        "name": "Small web images",
        "steps": [
            {"action": "image.resize", "params": {"width": 32}},
            {"action": "image.convert", "params": {"convert_to": "webp"}},
        ],
    }
    image = io.BytesIO()
    Image.new("RGB", (64, 48), "blue").save(image, format="PNG")

    with TestClient(app) as client:
        saved = client.post("/pipelines", json=pipeline)
        assert saved.status_code == 200
        pipeline_id = saved.json()["id"]
        assert len(client.get("/pipelines").json()["results"]) == 1

        response = client.post(
            "/pipelines/run",
            data={"pipeline": json.dumps(pipeline)},
            files=[
                ("files", ("one.png", image.getvalue(), "image/png")),
                ("files", ("two.png", image.getvalue(), "image/png")),
            ],
        )
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        assert len(jobs) == len(queued) == 2
        assert client.delete(f"/pipelines/{pipeline_id}").status_code == 200

    with Session(engine) as session:
        job = session.get(Job, uuid.UUID(jobs[0]["jobId"]))
        assert job.status == "pending"
        assert job.tool_used == "pipeline"
        assert job.output_filename == "one.processed.webp"
        assert (settings.UPLOAD_DIR / str(job.id) / job.input_filename).is_file()
        assert (settings.TEMP_DIR / str(job.id) / "pipeline.json").is_file()

    engine.dispose()


def test_pipeline_worker_creates_output_without_blocking_event_loop(tmp_path, monkeypatch):
    engine = _database()
    monkeypatch.setattr(job_manager_module, "engine", engine)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(settings, "TEMP_DIR", tmp_path / "temp")

    with Session(engine) as session:
        job = Job(
            input_filename="source.png",
            output_filename="source.processed.webp",
            input_format="png",
            output_format="webp",
            tool_used="pipeline",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    upload_dir = settings.UPLOAD_DIR / str(job_id)
    upload_dir.mkdir(parents=True)
    Image.new("RGB", (40, 20), "green").save(upload_dir / "source.png")
    recipe_dir = settings.TEMP_DIR / str(job_id)
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "pipeline.json").write_text(json.dumps({
        "steps": [
            {"action": "image.resize", "params": {"width": 20}},
            {"action": "image.convert", "params": {"convert_to": "webp"}},
        ],
    }), encoding="utf-8")

    async def process_and_tick():
        task = asyncio.create_task(JobManager()._process(str(job_id)))
        ticks = 0
        while not task.done():
            ticks += 1
            await asyncio.sleep(0.01)
        await task
        return ticks

    assert asyncio.run(process_and_tick()) > 0
    with Session(engine) as session:
        assert session.get(Job, job_id).status == "completed"
    with Image.open(settings.RESULTS_DIR / str(job_id) / "source.processed.webp") as result:
        assert result.size == (20, 10)

    engine.dispose()
