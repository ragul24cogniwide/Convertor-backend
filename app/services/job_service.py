import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any
from app.config import settings
from app.models.job import JobInfo, JobStatus, OutputFileInfo
from app.utils.file_utils import get_job_dirs, delete_job_workspace
from app.utils.validators import get_mime_type

logger = logging.getLogger("jobs")


class JobService:
    def __init__(self):
        # Fast memory cache for jobs
        self._jobs: Dict[str, JobInfo] = {}

    def create_job(
        self,
        job_id: str,
        original_filename: str,
        input_size: int,
        input_extension: str,
        target_format: str,
        conversion_type: str = "convert",
        options: Optional[Dict[str, Any]] = None
    ) -> JobInfo:
        job = JobInfo(
            job_id=job_id,
            status=JobStatus.PENDING,
            original_filename=original_filename,
            input_file_size=input_size,
            input_extension=input_extension,
            target_format=target_format,
            conversion_type=conversion_type,
            options=options or {},
            created_at=datetime.utcnow()
        )
        self._jobs[job_id] = job
        self._persist_job(job)
        return job

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        # Check cache
        if job_id in self._jobs:
            return self._jobs[job_id]
            
        # Try loading from disk
        job_root, _, _, _ = get_job_dirs(job_id)
        meta_file = job_root / "job.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    data = json.load(f)
                job = JobInfo(**data)
                self._jobs[job_id] = job
                return job
            except Exception as e:
                logger.error(f"Failed to read metadata for job {job_id}: {e}")
                
        return None

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None
    ) -> Optional[JobInfo]:
        job = self.get_job(job_id)
        if not job:
            return None
            
        job.status = status
        if error_message:
            job.error_message = error_message
            
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.utcnow()
            job.duration_seconds = round((job.completed_at - job.created_at).total_seconds(), 2)
            
        self._persist_job(job)
        return job

    def set_completed(
        self,
        job_id: str,
        output_files: List[Path]
    ) -> Optional[JobInfo]:
        job = self.get_job(job_id)
        if not job:
            return None
            
        file_infos = []
        for p in output_files:
            if p.exists():
                file_infos.append(
                    OutputFileInfo(
                        filename=p.name,
                        size_bytes=p.stat().st_size,
                        mime_type=get_mime_type(p.suffix)
                    )
                )
                
        job.output_files = file_infos
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.duration_seconds = round((job.completed_at - job.created_at).total_seconds(), 2)
        
        self._persist_job(job)
        return job

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
        return delete_job_workspace(job_id)

    def _persist_job(self, job: JobInfo):
        job_root, _, _, _ = get_job_dirs(job.job_id)
        if job_root.exists():
            meta_file = job_root / "job.json"
            try:
                with open(meta_file, "w") as f:
                    f.write(job.model_dump_json(indent=2))
            except Exception as e:
                logger.warning(f"Failed to persist job metadata {job.job_id}: {e}")


job_service = JobService()
