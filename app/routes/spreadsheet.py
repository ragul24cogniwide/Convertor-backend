from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from app.models.conversion import SpreadsheetPreviewResponse
from app.services.spreadsheet_service import spreadsheet_service
from app.utils.file_utils import create_job_workspace
from app.utils.security import sanitize_filename
from app.utils.validators import validate_uploaded_file

router = APIRouter(prefix="/api/spreadsheet", tags=["spreadsheet"])


@router.post("/preview", response_model=SpreadsheetPreviewResponse)
async def preview_spreadsheet(file: UploadFile = File(...), max_rows: int = 20):
    """Parses uploaded spreadsheet and returns structured JSON preview."""
    job_id, input_dir, _, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "sheet.xlsx")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        preview = spreadsheet_service.preview_data(path, max_rows=max_rows)
        return SpreadsheetPreviewResponse(**preview)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to preview spreadsheet: {str(e)}")


@router.post("/split-sheets")
async def split_spreadsheet_sheets(file: UploadFile = File(...), target_ext: str = Form("xlsx")):
    """Extracts each sheet into a separate file and returns a ZIP archive."""
    job_id, input_dir, output_dir, _ = create_job_workspace()
    safe_name = sanitize_filename(file.filename or "sheet.xlsx")
    path = input_dir / safe_name
    with open(path, "wb") as buff:
        buff.write(await file.read())
    validate_uploaded_file(path, safe_name)

    try:
        zip_path = spreadsheet_service.split_sheets(path, output_dir, target_ext=target_ext)
        return FileResponse(path=str(zip_path), media_type="application/zip", filename=zip_path.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Split sheets failed: {str(e)}")


@router.post("/merge")
async def merge_spreadsheets(files: List[UploadFile] = File(...)):
    """Merges multiple spreadsheets into a single multi-sheet Excel workbook."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 spreadsheets are required to merge.")

    job_id, input_dir, output_dir, _ = create_job_workspace()
    saved_paths = []
    for f in files:
        safe_name = sanitize_filename(f.filename or "sheet.xlsx")
        path = input_dir / safe_name
        with open(path, "wb") as buff:
            buff.write(await f.read())
        validate_uploaded_file(path, safe_name)
        saved_paths.append(path)

    try:
        merged_file = spreadsheet_service.merge_spreadsheets(saved_paths, output_dir)
        return FileResponse(
            path=str(merged_file),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=merged_file.name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Merge spreadsheets failed: {str(e)}")
