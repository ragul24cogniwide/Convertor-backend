from fastapi import APIRouter
from app.config import settings
from app.models.health import HealthResponse, DependencyStatus
from app.services.office_service import office_service
from app.services.ocr_service import ocr_service
import fitz
import PIL
import pandas
import openpyxl

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    # Dependency detections
    lo_installed = office_service.has_libreoffice
    lo_ver = office_service.get_version() if lo_installed else None
    
    tess_installed = ocr_service.is_available
    tess_ver = ocr_service.get_version() if tess_installed else None
    ocr_langs = ocr_service.get_installed_languages() if tess_installed else []

    dependencies = {
        "libreoffice": DependencyStatus(
            name="LibreOffice Headless",
            installed=lo_installed,
            version=lo_ver,
            path=office_service.soffice_bin,
            details="Required for DOCX → PDF, PPTX → PDF, and ODT conversions." if not lo_installed else "Active"
        ),
        "tesseract": DependencyStatus(
            name="Tesseract OCR",
            installed=tess_installed,
            version=tess_ver,
            path=ocr_service.tesseract_bin,
            details="Required for Optical Character Recognition (Searchable PDF, Text extraction)." if not tess_installed else f"Languages: {', '.join(ocr_langs)}"
        ),
        "pymupdf": DependencyStatus(
            name="PyMuPDF (MuPDF)",
            installed=True,
            version=fitz.__version__,
            details="Native C-engine for PDF manipulation, rasterization, and vector rendering."
        ),
        "pillow": DependencyStatus(
            name="Pillow",
            installed=True,
            version=PIL.__version__,
            details="Native imaging library for format conversions, optimization, and transformation."
        )
    }

    services = {
        "pdf": True,
        "office": lo_installed,
        "image": True,
        "spreadsheet": True,
        "ocr": tess_installed,
        "archive": True,
        "text": True,
        "ebook": True
    }

    return HealthResponse(
        status="ok",
        services=services,
        dependencies=dependencies,
        ocr_languages=ocr_langs,
        max_file_size_mb=settings.MAX_FILE_SIZE_MB,
        temp_file_ttl_minutes=settings.TEMP_FILE_TTL_MINUTES
    )
