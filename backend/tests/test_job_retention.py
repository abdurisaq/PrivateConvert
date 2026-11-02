from datetime import datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.core import job_retention
from app.core.config import settings
from app.models import Job, JobPreference


def test_purge_removes_expired_terminal_jobs_and_their_files(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(job_retention, "engine", engine)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(settings, "TEMP_DIR", tmp_path / "temp")
    now = datetime.utcnow()

    with Session(engine) as session:
        expired = Job(
            input_filename="old.png",
            output_filename="old.webp",
            input_format="png",
            output_format="webp",
            status="completed",
            created_at=now - timedelta(days=31),
        )
        active = Job(
            input_filename="active.png",
            output_filename="active.webp",
            input_format="png",
            output_format="webp",
            status="processing",
            created_at=now - timedelta(days=40),
        )
        session.add_all([expired, active, JobPreference(retention="normal")])
        session.commit()
        expired_id, active_id = expired.id, active.id

        upload = settings.UPLOAD_DIR / str(expired_id)
        upload.mkdir(parents=True)
        (upload / "input").write_bytes(b"input")
        assert job_retention.purge_expired_jobs(session, now) == 1
        assert session.get(Job, expired_id) is None
        assert session.get(Job, active_id) is not None
        assert not upload.exists()

    engine.dispose()


def test_job_retention_settings_validate_and_persist():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.api.routes.jobs import router

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def database_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(router, prefix="/jobs")
    app.dependency_overrides[get_db] = database_session

    with TestClient(app) as client:
        assert client.get("/jobs/settings").json()["retention"] == "normal"
        updated = client.put("/jobs/settings", json={"retention": "7d"})
        invalid = client.put("/jobs/settings", json={"retention": "tomorrow"})

    assert updated.status_code == 200
    assert updated.json()["retention"] == "7d"
    assert invalid.status_code == 422
    engine.dispose()
