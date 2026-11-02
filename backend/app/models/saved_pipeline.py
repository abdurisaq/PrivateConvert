import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class SavedPipeline(SQLModel, table=True):
    __tablename__ = "saved_pipelines"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    definition: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
