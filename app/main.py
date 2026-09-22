import asyncio
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routes import health, conversion, jobs, pdf, spreadsheet, image, ocr
from app.services.office_service import office_service
from app.services.ocr_service import ocr_service
from app.utils.cleanup import periodic_cleanup_task

# Configure clean, privacy-conscious logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("convertor_app")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Check system conversion dependencies
    logger.info("=" * 60)
    logger.info("Initializing Private Document Converter...")
    logger.info("Privacy Guarantee: ZERO external network calls. All processing is 100% local.")
    
    if office_service.has_libreoffice:
        logger.info(f"LibreOffice detected: {office_service.get_version()}")
    else:
        logger.warning(
            "LibreOffice is NOT installed. DOCX->PDF and presentation conversions will require "
            "LibreOffice installation or running via Docker."
        )

    if ocr_service.is_available:
        langs = ocr_service.get_installed_languages()
        logger.info(f"Tesseract OCR detected: v{ocr_service.get_version()} (Languages: {', '.join(langs)})")
    else:
        logger.warning(
            "Tesseract OCR is NOT installed. OCR capabilities will be disabled until installed."
        )

    # Launch background auto-cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup_task())
    logger.info(f"Ephemeral cleanup worker scheduled every {settings.CLEANUP_INTERVAL_MINUTES} minutes.")
    logger.info("=" * 60)

    yield

    # Shutdown: Cancel background cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Private Document Converter backend shut down cleanly.")


app = FastAPI(
    title="Private Document Converter API",
    description=(
        "Production-grade, privacy-first, self-hosted document conversion API.\n\n"
        "**Privacy Architecture Guarantee:**\n"
        "- All conversion engines (PyMuPDF, pdf2docx, Pillow, pandas, LibreOffice, Tesseract) run strictly locally.\n"
        "- No files or contents are ever sent to any third-party cloud service or AI provider.\n"
        "- Uploaded and converted files are automatically purged after the retention TTL."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler (Prevent internal traceback leaks to frontend)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error during request to {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred during conversion processing."}
    )

# Register route modules
app.include_router(health.router)
app.include_router(conversion.router)
app.include_router(jobs.router)
app.include_router(pdf.router)
app.include_router(spreadsheet.router)
app.include_router(image.router)
app.include_router(ocr.router)


@app.get("/")
async def root():
    return {
        "message": "Private Document Converter API is running.",
        "privacy": "Files are processed locally and never leave this host.",
        "docs": "/docs",
        "health": "/api/health",
        "conversions": "/api/conversions"
    }
