import json
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from app.services.image_service import image_service
from app.utils.file_utils import create_job_workspace
from app.utils.security import sanitize_filename
from app.utils.validators import validate_uploaded_file, get_mime_type

router = APIRouter(prefix="/api/image", tags=["image"])


@router.post("/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    target_format: Optional[str] = Form(None),
    quality: int = Form(85),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    scale_percent: Optional[int] = Form(None),
    rotate_angle: Optional[int] = Form(None),
    strip_metadata: bool = Form(False)
):
    """Resizes, rotates, compresses, or strips metadata from an image."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "image.png")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    target_fmt = target_format or path.suffix.lower().lstrip(".")
    options = {
        "quality": quality,
        "width": width,
        "height": height,
        "scale_percent": scale_percent,
        "rotate_angle": rotate_angle,
        "strip_metadata": strip_metadata
    }

    try:
        outputs = image_service.convert(path, target_fmt, output_dir, options)
        out_file = outputs[0]
        return FileResponse(path=str(out_file), media_type=get_mime_type(out_file.name), filename=out_file.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image optimization failed: {str(e)}")


@router.post("/combine-to-pdf")
async def combine_images_to_pdf(files: List[UploadFile] = File(...)):
    """Combines multiple uploaded images into a single PDF album."""
    if len(files) < 1:
        raise HTTPException(status_code=400, detail="At least 1 image file is required.")

    job_id, input_dir, output_dir, _ = create_job_workspace()
    saved_paths = []
    for f in files:
        safe_name = sanitize_filename(f.filename or "photo.jpg")
        path = input_dir / safe_name
        with open(path, "wb") as buff:
            buff.write(await f.read())
        validate_uploaded_file(path, safe_name)
        saved_paths.append(path)

    try:
        pdf_path = image_service.images_to_pdf(saved_paths, output_dir, "album.pdf")
        return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=pdf_path.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Combine images to PDF failed: {str(e)}")
