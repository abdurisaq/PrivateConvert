from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Private Converter"
    DEBUG: bool = Field(default=False, env="DEBUG")
    DATABASE_URL: str = Field(default="sqlite:///./db.sqlite3", env="DATABASE_URL")
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    UPLOAD_DIR: Path = Field(default="data/uploads", env="UPLOAD_DIR")
    RESULTS_DIR: Path = Field(default="data/results", env="RESULTS_DIR")
    TEMP_DIR: Path = Field(default="data/temp", env="TEMP_DIR")
    MAX_FILE_SIZE: int = Field(default=1073741824, env="MAX_FILE_SIZE")
    MAX_CONCURRENT_PROCESSES: int = Field(default=4, env="MAX_CONCURRENT_PROCESSES")
    PROCESS_TIMEOUT: int = Field(default=300, env="PROCESS_TIMEOUT")
    API_V1_STR: str = Field(default="/api", env="API_V1_STR")

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.UPLOAD_DIR = self.BASE_DIR / self.UPLOAD_DIR
        self.RESULTS_DIR = self.BASE_DIR / self.RESULTS_DIR
        self.TEMP_DIR = self.BASE_DIR / self.TEMP_DIR
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
