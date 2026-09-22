from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from app.models.job import JobInfo
from app.services.job_service import job_service
from app.services.archive_service import archive_service
from app.utils.file_utils import get_job_dirs
from app.utils.validators import get_mime_type

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobInfo)
async def get_job_status(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or has expired."
        )
    return job


@router.get("/{job_id}/download")
async def download_job_result(job_id: str, zip_all: bool = False):
    """
    Downloads the converted file for a job.
    If there are multiple files or zip_all=True, downloads a single ZIP archive.
    """
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or has expired."
        )

    if job.status != "completed" or not job.output_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversion has not completed or has failed."
        )

    job_root, _, output_dir, _ = get_job_dirs(job_id)
    
    # If single file and not zip_all requested
    if len(job.output_files) == 1 and not zip_all:
        file_info = job.output_files[0]
        file_path = output_dir / file_info.filename
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found on disk.")
            
        media_type = file_info.mime_type or get_mime_type(file_info.filename)
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_info.filename
        )

    # Multiple files: package as zip
    zip_filename = f"{Path(job.original_filename).stem}_converted.zip"
    zip_path = output_dir / zip_filename
    
    files_to_zip = [output_dir / f.filename for f in job.output_files if (output_dir / f.filename).exists()]
    archive_service.create_zip(files_to_zip, zip_path)

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=zip_filename
    )


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """
    Deletes the temporary files for the job immediately upon user request.
    """
    deleted = job_service.delete_job(job_id)
    return {"job_id": job_id, "deleted": deleted, "message": "Job workspace purged."}
