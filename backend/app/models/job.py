from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    input_filename: str
    output_filename: str
    input_format: str
    output_format: str
    status: str = Field(default="pending")
    progress: int = Field(default=0)
    file_size: int = Field(default=0)
    error_message: Optional[str] = None
    tool_used: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Job {self.input_filename} -> {self.output_filename} ({self.status})>"
