import os
from pathlib import Path
from typing import List, Union, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    APP_NAME: str = "Private Document Converter"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8103
    
    # File limits
    MAX_FILE_SIZE_MB: int = 100
    
    # TTL & Cleanup
    TEMP_FILE_TTL_MINUTES: int = 30
    CLEANUP_INTERVAL_MINUTES: int = 5
    CONVERSION_TIMEOUT_SECONDS: int = 120
    
    # CORS - includes deployed frontend and local development
    CORS_ORIGINS: Union[str, List[str]] = (
        "http://20.235.56.85:3221,"
        "https://convertor-frontend.vercel.app,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )
    
    # Storage
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    TEMP_DIR: Optional[Path] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip().rstrip("/") for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [origin.rstrip("/") for origin in v]
        return v

    def model_post_init(self, __context):
        if self.TEMP_DIR is None:
            self.TEMP_DIR = self.BASE_DIR / "temp"
        elif not Path(self.TEMP_DIR).is_absolute():
            self.TEMP_DIR = self.BASE_DIR / self.TEMP_DIR
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
