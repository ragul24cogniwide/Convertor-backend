import json
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from app.services.pdf_service import pdf_service
from app.utils.file_utils import create_job_workspace
from app.utils.security import sanitize_filename
from app.utils.validators import validate_uploaded_file

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


def parse_page_ranges(range_str: str) -> List[int]:
    """Parses comma-separated numbers and ranges (e.g. '1-3, 5, 8') into 0-indexed page numbers."""
    pages = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start = max(1, int(start_s.strip()))
                end = int(end_s.strip())
                for p in range(start, end + 1):
                    if (p - 1) not in pages:
                        pages.append(p - 1)
            except Exception:
                pass
        elif part.isdigit():
            idx = int(part) - 1
            if idx not in pages:
                pages.append(idx)
    return sorted(pages)


@router.post("/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    """Merges multiple uploaded PDF files into one."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 PDF files are required to merge.")

    job_id, input_dir, output_dir, _ = create_job_workspace()
    saved_paths = []

    for f in files:
        safe_name = sanitize_filename(f.filename or "doc.pdf")
        path = input_dir / safe_name
        content = await f.read()
        with open(path, "wb") as buff:
            buff.write(content)
        validate_uploaded_file(path, safe_name)
        saved_paths.append(path)

    try:
        merged_pdf = pdf_service.merge_pdfs(saved_paths, output_dir, "merged.pdf")
        return FileResponse(path=str(merged_pdf), media_type="application/pdf", filename="merged.pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF Merge failed: {str(e)}")


@router.post("/split")
async def split_pdf(
    file: UploadFile = File(...),
    pages: Optional[str] = Form(None),
    mode: str = Form("pages"),
    chunk_size: int = Form(1)
):
    """Splits PDF by comma-separated page numbers/ranges, burst all, or chunk size."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    page_list = None
    chunk = None
    if mode == "chunk":
        chunk = max(1, chunk_size)
    elif mode == "pages" and pages:
        page_list = parse_page_ranges(pages)

    try:
        outputs = pdf_service.split_pdf(path, output_dir, pages=page_list, chunk_size=chunk)
        if len(outputs) == 1:
            return FileResponse(path=str(outputs[0]), media_type="application/pdf" if outputs[0].suffix == ".pdf" else "application/zip", filename=outputs[0].name)
        return FileResponse(path=str(outputs[0]), filename=outputs[0].name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF Split failed: {str(e)}")


@router.post("/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    quality: int = Form(65),
    dpi: Optional[int] = Form(150),
    grayscale: bool = Form(False),
    strip_metadata: bool = Form(True)
):
    """Compresses PDF document with adjustable quality, downsampling, and metadata stripping."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        compressed = pdf_service.compress_pdf(
            path,
            output_dir,
            quality=quality,
            dpi=dpi,
            grayscale=grayscale,
            strip_metadata=strip_metadata
        )
        return FileResponse(path=str(compressed), media_type="application/pdf", filename=compressed.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF compression failed: {str(e)}")


@router.post("/rotate")
async def rotate_pdf(
    file: UploadFile = File(...),
    angle: int = Form(90),
    scope: str = Form("all"),
    pages: Optional[str] = Form(None)
):
    """Rotates PDF pages."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    page_list = parse_page_ranges(pages) if (scope == "custom" and pages) else None

    try:
        rotated = pdf_service.rotate_pdf(path, output_dir, angle=angle, pages=page_list, scope=scope)
        return FileResponse(path=str(rotated), media_type="application/pdf", filename=rotated.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF rotation failed: {str(e)}")


@router.post("/watermark")
async def watermark_pdf(
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIAL"),
    opacity: float = Form(0.3),
    size: int = Form(36),
    color: str = Form("gray"),
    angle: int = Form(45),
    on_top: bool = Form(True)
):
    """Adds a text watermark to every page in PDF with customizable angle, color, and layer position."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        watermarked = pdf_service.add_watermark(
            path,
            output_dir,
            watermark_text=text,
            opacity=opacity,
            fontsize=size,
            color_name=color,
            angle=angle,
            on_top=on_top
        )
        return FileResponse(path=str(watermarked), media_type="application/pdf", filename=watermarked.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF watermark failed: {str(e)}")


@router.post("/protect")
async def protect_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    owner_password: Optional[str] = Form(None),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(False)
):
    """Encrypts PDF with password and customizable permission flags."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        protected = pdf_service.password_protect(
            path,
            output_dir,
            user_password=password,
            owner_password=owner_password,
            allow_print=allow_print,
            allow_copy=allow_copy
        )
        return FileResponse(path=str(protected), media_type="application/pdf", filename=protected.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF protection failed: {str(e)}")


@router.post("/unlock")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    """Removes password encryption from PDF."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        unprotected = pdf_service.remove_password(path, output_dir, password=password)
        return FileResponse(path=str(unprotected), media_type="application/pdf", filename=unprotected.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF unlock failed: {str(e)}")


@router.post("/delete-pages")
async def delete_pdf_pages(file: UploadFile = File(...), pages: str = Form(...)):
    """Deletes specific pages from PDF."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    pages_to_del = parse_page_ranges(pages)
    if not pages_to_del:
        raise HTTPException(status_code=400, detail="Please provide valid page numbers to delete.")

    try:
        result_pdf = pdf_service.delete_pages(path, output_dir, pages_to_del)
        return FileResponse(path=str(result_pdf), media_type="application/pdf", filename=result_pdf.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Delete pages failed: {str(e)}")


@router.post("/add-page-numbers")
async def add_page_numbers_endpoint(
    file: UploadFile = File(...),
    format_pattern: str = Form("Page {page} of {total}"),
    position: str = Form("bottom_center"),
    start_page: int = Form(1),
    size: int = Form(10)
):
    """Adds customized page numbers to PDF."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        result_pdf = pdf_service.add_page_numbers(
            path,
            output_dir,
            format_pattern=format_pattern,
            position=position,
            start_page=start_page,
            fontsize=size
        )
        return FileResponse(path=str(result_pdf), media_type="application/pdf", filename=result_pdf.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Add page numbers failed: {str(e)}")


@router.post("/extract-images")
async def extract_pdf_images(
    file: UploadFile = File(...),
    min_dimension: int = Form(50),
    output_format: str = Form("original")
):
    """Extracts all embedded images into a ZIP archive with filtering and format options."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "doc.pdf")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        zip_out = pdf_service.extract_images(
            path,
            output_dir,
            min_dimension=min_dimension,
            output_format=output_format
        )
        return FileResponse(path=str(zip_out), media_type="application/zip", filename=zip_out.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image extraction failed: {str(e)}")
