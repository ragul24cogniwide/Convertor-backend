import os
import re
import shlex
import subprocess
import zipfile
from pathlib import Path
from typing import List, Optional


# Filename sanitization pattern: allow letters, numbers, dashes, underscores, dots
SAFE_FILENAME_REGEX = re.compile(r'[^a-zA-Z0-9._-]')

# Magic bytes signature dictionary
MAGIC_BYTES = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "bmp": [b"BM"],
    "tiff": [b"II*\x00", b"MM\x00*"],
    "tif": [b"II*\x00", b"MM\x00*"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],  # Also docx, xlsx, pptx, epub are ZIP containers
    "docx": [b"PK\x03\x04"],
    "xlsx": [b"PK\x03\x04"],
    "pptx": [b"PK\x03\x04"],
    "epub": [b"PK\x03\x04"],
    "odt": [b"PK\x03\x04"],
    "odp": [b"PK\x03\x04"],
    "ods": [b"PK\x03\x04"],
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes user-provided filename to prevent path traversal and shell injection.
    Strips directory paths and replaces illegal characters with underscores.
    """
    # Extract only the base name
    base_name = os.path.basename(filename.strip().replace("\\", "/"))
    # Separate stem and extension
    stem, ext = os.path.splitext(base_name)
    
    # Sanitize stem
    safe_stem = SAFE_FILENAME_REGEX.sub("_", stem)
    safe_stem = re.sub(r'_+', '_', safe_stem).strip("._")
    if not safe_stem:
        safe_stem = "file"
        
    # Sanitize extension (keep only alphanumeric)
    safe_ext = re.sub(r'[^a-zA-Z0-9]', '', ext).lower()
    if safe_ext:
        return f"{safe_stem}.{safe_ext}"
    return safe_stem


def prevent_path_traversal(base_dir: Path, target_path: Path) -> Path:
    """
    Verifies that target_path resolves strictly within base_dir.
    Raises ValueError if path traversal is detected.
    """
    resolved_base = base_dir.resolve()
    resolved_target = target_path.resolve()
    
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError:
        raise ValueError("Access denied: path traversal attempt detected.")
        
    return resolved_target


def validate_file_signature(file_path: Path, expected_extension: str) -> bool:
    """
    Validates the file header against known magic bytes for common formats.
    Returns True if valid or if extension is text-based (no fixed magic bytes).
    """
    ext = expected_extension.lower().lstrip(".")
    signatures = MAGIC_BYTES.get(ext)
    
    if not signatures:
        # Formats like txt, csv, tsv, md, html, rtf don't use binary magic headers
        return True
        
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            
        for sig in signatures:
            if header.startswith(sig):
                return True
                
        # For webp, check RIFF....WEBP
        if ext == "webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return True
            
        return False
    except Exception:
        return False


def validate_zip_archive(zip_path: Path, max_total_size: int = 200 * 1024 * 1024, max_files: int = 1000) -> None:
    """
    Validates a ZIP archive against Zip-Slip, path traversal, and decompression bombs.
    Raises ValueError if unsafe.
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Uploaded file is not a valid ZIP archive.")
        
    with zipfile.ZipFile(zip_path, 'r') as zf:
        infolist = zf.infolist()
        
        if len(infolist) > max_files:
            raise ValueError(f"ZIP contains too many files ({len(infolist)} > {max_files}).")
            
        total_uncompressed = 0
        for info in infolist:
            filename = info.filename
            
            # Check for path traversal in entry names
            if filename.startswith("/") or filename.startswith("\\") or ".." in filename.split("/"):
                raise ValueError(f"Dangerous ZIP entry detected: {filename}")
                
            total_uncompressed += info.file_size
            if total_uncompressed > max_total_size:
                raise ValueError("ZIP decompression bomb detected: exceeds uncompressed size limit.")


def safe_subprocess_run(
    cmd_args: List[str],
    timeout: int = 120,
    cwd: Optional[Path] = None
) -> subprocess.CompletedProcess:
    """
    Executes an external command safely:
    - Never uses shell=True
    - Strict timeout enforcement
    - Captures stdout/stderr
    """
    if not isinstance(cmd_args, list) or not all(isinstance(a, str) for a in cmd_args):
        raise ValueError("Command arguments must be a list of strings.")
        
    try:
        result = subprocess.run(
            cmd_args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None
        )
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command '{cmd_args[0]}' timed out after {timeout} seconds.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Command '{cmd_args[0]}' not found on the system.")
