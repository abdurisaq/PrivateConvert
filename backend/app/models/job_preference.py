from sqlmodel import Field, SQLModel


class JobPreference(SQLModel, table=True):
    __tablename__ = "job_preferences"

    id: int = Field(default=1, primary_key=True)
    retention: str = Field(default="normal", max_length=16)
