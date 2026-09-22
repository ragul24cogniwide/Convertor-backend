from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class OutputFileInfo(BaseModel):
    filename: str
    size_bytes: int
    mime_type: Optional[str] = None


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    original_filename: str
    input_file_size: int
    input_extension: str
    target_format: str
    conversion_type: Optional[str] = "convert"
    options: Dict[str, Any] = Field(default_factory=dict)
    output_files: List[OutputFileInfo] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    download_count: int = 0
