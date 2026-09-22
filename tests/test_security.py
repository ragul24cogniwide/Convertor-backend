import io
import pytest
import zipfile
from pathlib import Path
from app.utils.security import (
    sanitize_filename,
    prevent_path_traversal,
    validate_zip_archive,
    validate_file_signature
)


def test_sanitize_filename():
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32.dll") == "system32.dll"
    assert sanitize_filename("my document (1) [final].pdf") == "my_document_1_final.pdf"
    assert sanitize_filename("safe-name_123.docx") == "safe-name_123.docx"
    assert sanitize_filename("....hidden.txt") == "hidden.txt"
    assert sanitize_filename("") == "file"


def test_prevent_path_traversal(tmp_path):
    base_dir = tmp_path / "allowed"
    base_dir.mkdir()
    
    # Safe path inside
    safe_target = base_dir / "subdir" / "file.txt"
    assert prevent_path_traversal(base_dir, safe_target) == safe_target.resolve()

    # Escape attempt
    evil_target = base_dir / ".." / "secret.txt"
    with pytest.raises(ValueError, match="Access denied"):
        prevent_path_traversal(base_dir, evil_target)


def test_validate_zip_archive_safe(tmp_path):
    zip_path = tmp_path / "safe.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test.txt", "Hello World")
        zf.writestr("folder/doc.pdf", "Dummy PDF content")

    # Should not raise
    validate_zip_archive(zip_path)


def test_validate_zip_archive_path_traversal(tmp_path):
    zip_path = tmp_path / "evil_slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:")

    with pytest.raises(ValueError, match="Dangerous ZIP entry detected"):
        validate_zip_archive(zip_path)


def test_file_signature_validation(tmp_path):
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.5 test content")
    assert validate_file_signature(pdf_file, "pdf") is True

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"NOT_A_PDF_HEADER")
    assert validate_file_signature(fake_pdf, "pdf") is False

    png_file = tmp_path / "sample.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    assert validate_file_signature(png_file, "png") is True
