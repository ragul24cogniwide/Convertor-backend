import mimetypes
from pathlib import Path
from typing import Set, Tuple
from fastapi import HTTPException, UploadFile, status
from app.config import settings
from app.utils.security import validate_file_signature


# Supported file extensions mapped by category
SUPPORTED_EXTENSIONS: Set[str] = {
    # PDF
    "pdf",
    # Office / Word
    "docx", "doc", "odt", "rtf",
    # Spreadsheets
    "xlsx", "xls", "csv", "ods", "tsv",
    # Presentations
    "pptx", "ppt", "odp",
    # Images
    "jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif", "svg", "ico",
    # Text / Markdown / HTML
    "txt", "md", "html", "htm",
    # Ebook
    "epub",
    # Archive
    "zip"
}

# Standard MIME type fallbacks
MIME_TYPE_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "txt": "text/plain",
    "md": "text/markdown",
    "html": "text/html",
    "htm": "text/html",
    "epub": "application/epub+zip",
    "zip": "application/zip",
}


def get_file_extension(filename: str) -> str:
    """Extracts lowercased file extension without leading dot."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext


def validate_file_extension(filename: str) -> str:
    """Validates that file extension is supported."""
    ext = get_file_extension(filename)
    if not ext or ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{ext if ext else 'unknown'}. Please check supported formats."
        )
    return ext


def validate_file_size(size_bytes: int) -> None:
    """Validates that file size does not exceed MAX_FILE_SIZE_MB."""
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB."
        )
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )


def validate_uploaded_file(file_path: Path, filename: str) -> str:
    """
    Validates extension, size, and header signature.
    Returns the normalized extension.
    """
    ext = validate_file_extension(filename)
    size = file_path.stat().st_size
    validate_file_size(size)
    
    if not validate_file_signature(file_path, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file content does not match the .{ext} format signature."
        )
        
    return ext


def get_mime_type(ext_or_filename: str) -> str:
    """Returns MIME type for extension or filename."""
    ext = get_file_extension(ext_or_filename) if "." in ext_or_filename else ext_or_filename.lower()
    return MIME_TYPE_MAP.get(ext, mimetypes.guess_type(f"file.{ext}")[0] or "application/octet-stream")
