import json
import logging
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.config import settings
from app.models.conversion import ConversionRegistryResponse, ConvertResponse
from app.models.job import JobStatus
from app.services.conversion_dispatcher import get_conversion_registry, execute_conversion
from app.services.job_service import job_service
from app.utils.file_utils import create_job_workspace
from app.utils.security import sanitize_filename
from app.utils.validators import validate_uploaded_file

logger = logging.getLogger("conversion_route")
router = APIRouter(prefix="/api", tags=["conversion"])


@router.get("/conversions", response_model=ConversionRegistryResponse)
async def list_conversions():
    """Returns dynamic conversion matrix based on local system capabilities."""
    return get_conversion_registry()


@router.post("/convert", response_model=ConvertResponse)
async def convert_file(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    conversion_type: str = Form("convert"),
    options: str = Form("{}")
):
    """
    Universal conversion endpoint.
    Accepts multipart upload, validates file, executes conversion locally,
    and returns job tracking details and download URL.
    """
    start_time = time.time()
    
    # 1. Parse JSON options
    try:
        parsed_options = json.loads(options) if options else {}
    except Exception:
        parsed_options = {}

    # 2. Sanitize original filename
    original_name = file.filename or "uploaded_file"
    safe_name = sanitize_filename(original_name)

    # 3. Create isolated job workspace
    job_id, input_dir, output_dir, work_dir = create_job_workspace()
    dest_input_path = input_dir / safe_name

    # 4. Stream upload to disk to preserve memory
    try:
        total_bytes = 0
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        with open(dest_input_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    dest_input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB."
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream upload: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save uploaded file.")

    # 5. Validate file extension, size, and header
    ext = validate_uploaded_file(dest_input_path, safe_name)

    # 6. Initialize job record
    job_info = job_service.create_job(
        job_id=job_id,
        original_filename=safe_name,
        input_size=total_bytes,
        input_extension=ext,
        target_format=target_format,
        conversion_type=conversion_type,
        options=parsed_options
    )
    job_service.update_status(job_id, JobStatus.PROCESSING)

    # 7. Execute conversion locally
    try:
        output_files = execute_conversion(
            input_path=dest_input_path,
            target_format=target_format,
            conversion_type=conversion_type,
            output_dir=output_dir,
            options=parsed_options
        )
        
        if not output_files:
            raise RuntimeError("Conversion produced no output files.")

        job_service.set_completed(job_id, output_files)
        
        duration = round(time.time() - start_time, 2)
        logger.info(f"[INFO] job={job_id} conversion={ext}_to_{target_format} status=completed duration={duration}s")

        primary_output = output_files[0].name
        return ConvertResponse(
            job_id=job_id,
            status="completed",
            target_format=target_format,
            output_filename=primary_output,
            output_files=[f.name for f in output_files],
            download_url=f"/api/jobs/{job_id}/download"
        )

    except Exception as e:
        job_service.update_status(job_id, JobStatus.FAILED, error_message=str(e))
        logger.error(f"[ERROR] job={job_id} conversion={ext}_to_{target_format} error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
