import pytest
from fastapi import HTTPException
from app.utils.validators import (
    get_file_extension,
    validate_file_extension,
    validate_file_size,
    get_mime_type
)


def test_get_file_extension():
    assert get_file_extension("document.PDF") == "pdf"
    assert get_file_extension("my.file.tar.gz") == "gz"
    assert get_file_extension("no_ext") == ""


def test_validate_file_extension():
    assert validate_file_extension("report.docx") == "docx"
    assert validate_file_extension("sheet.xlsx") == "xlsx"
    assert validate_file_extension("scan.png") == "png"

    with pytest.raises(HTTPException) as exc:
        validate_file_extension("malware.exe")
    assert exc.value.status_code == 400
    assert "Unsupported file type" in exc.value.detail


def test_validate_file_size():
    # Empty file
    with pytest.raises(HTTPException) as exc:
        validate_file_size(0)
    assert exc.value.status_code == 400

    # Normal file
    validate_file_size(1024 * 1024)

    # Oversized file (> 100 MB)
    with pytest.raises(HTTPException) as exc:
        validate_file_size(150 * 1024 * 1024)
    assert exc.value.status_code == 413


def test_get_mime_type():
    assert get_mime_type("doc.pdf") == "application/pdf"
    assert get_mime_type("photo.png") == "image/png"
    assert get_mime_type("table.csv") == "text/csv"
