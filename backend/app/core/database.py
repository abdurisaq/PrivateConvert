from sqlmodel import SQLModel, create_engine

from app.core.config import settings

engine = create_engine(str(settings.DATABASE_URL), echo=settings.DEBUG)


def init_db() -> None:
    SQLModel.metadata.create_all(bind=engine)
