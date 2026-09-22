from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from app.services.ocr_service import ocr_service
from app.utils.file_utils import create_job_workspace
from app.utils.security import sanitize_filename
from app.utils.validators import validate_uploaded_file, get_mime_type

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/process")
async def process_ocr(
    file: UploadFile = File(...),
    target_format: str = Form("pdf"),  # "pdf" for searchable PDF, "txt" for text
    language: str = Form("eng")
):
    """
    Performs local offline Optical Character Recognition (OCR) via Tesseract.
    Produces either a Searchable PDF or Plain Text file.
    Supports English ('eng'), Tamil ('tam'), or other installed languages.
    """
    if not ocr_service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tesseract OCR is not installed on this server. Please install tesseract-ocr (and tesseract-ocr-tam) or run via Docker."
        )

    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "scan.png")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    options = {"language": language}
    try:
        outputs = ocr_service.convert(path, target_format, output_dir, options)
        out_file = outputs[0]
        return FileResponse(
            path=str(out_file),
            media_type=get_mime_type(out_file.name),
            filename=out_file.name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OCR processing failed: {str(e)}")
