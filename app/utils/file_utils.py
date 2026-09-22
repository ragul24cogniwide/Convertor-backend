import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple
from app.config import settings
from app.utils.security import sanitize_filename, prevent_path_traversal


def create_job_workspace(custom_job_id: str = None) -> Tuple[str, Path, Path, Path]:
    """
    Creates an isolated temporary workspace for a conversion job:
    temp/{job_id}/
      ├── input/
      ├── output/
      └── work/
    Returns (job_id, input_dir, output_dir, work_dir)
    """
    job_id = custom_job_id or str(uuid.uuid4())
    job_root = settings.TEMP_DIR / job_id
    
    input_dir = job_root / "input"
    output_dir = job_root / "output"
    work_dir = job_root / "work"
    
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    return job_id, input_dir, output_dir, work_dir


def get_job_dirs(job_id: str) -> Tuple[Path, Path, Path, Path]:
    """Returns (job_root, input_dir, output_dir, work_dir) for given job_id."""
    job_root = settings.TEMP_DIR / sanitize_filename(job_id)
    return job_root, job_root / "input", job_root / "output", job_root / "work"


def delete_job_workspace(job_id: str) -> bool:
    """
    Completely and securely deletes all temporary files associated with a job.
    Returns True if directory existed and was removed.
    """
    job_root, _, _, _ = get_job_dirs(job_id)
    try:
        # Prevent escaping temp dir
        prevent_path_traversal(settings.TEMP_DIR, job_root)
        if job_root.exists() and job_root.is_dir():
            shutil.rmtree(job_root, ignore_errors=True)
            return True
    except Exception:
        pass
    return False
