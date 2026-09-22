from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    services: Dict[str, bool]
    dependencies: Dict[str, DependencyStatus]
    ocr_languages: List[str] = Field(default_factory=list)
    max_file_size_mb: int
    temp_file_ttl_minutes: int
