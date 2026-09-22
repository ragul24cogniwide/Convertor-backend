import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import settings
from app.models.conversion import ConversionRegistryResponse, CategoryConversions, ConversionOption
from app.services.pdf_service import pdf_service
from app.services.office_service import office_service
from app.services.spreadsheet_service import spreadsheet_service
from app.services.image_service import image_service
from app.services.text_service import text_service
from app.services.ebook_service import ebook_service
from app.services.ocr_service import ocr_service
from app.services.archive_service import archive_service

logger = logging.getLogger("conversion_dispatcher")


def get_conversion_registry() -> ConversionRegistryResponse:
    has_lo = office_service.has_libreoffice
    has_tess = ocr_service.is_available

    categories = {
        "pdf": CategoryConversions(
            category_id="pdf",
            name="PDF Documents",
            description="Convert PDF to editable formats, images, tables, or presentations",
            formats=["pdf"],
            conversions=[
                ConversionOption(id="pdf_docx", name="PDF to Word (DOCX)", category="pdf", input_format="pdf", output_format="docx", description="Extract formatted text, tables and headings to Word"),
                ConversionOption(id="pdf_txt", name="PDF to Plain Text (TXT)", category="pdf", input_format="pdf", output_format="txt", description="Extract pure text content from all pages"),
                ConversionOption(id="pdf_html", name="PDF to HTML", category="pdf", input_format="pdf", output_format="html", description="Render PDF pages into readable HTML"),
                ConversionOption(id="pdf_png", name="PDF to PNG Images", category="pdf", input_format="pdf", output_format="png", description="High-resolution rasterization of each page"),
                ConversionOption(id="pdf_jpg", name="PDF to JPG Images", category="pdf", input_format="pdf", output_format="jpg", description="Compressed JPEG render of each page"),
                ConversionOption(id="pdf_svg", name="PDF to SVG Vector", category="pdf", input_format="pdf", output_format="svg", description="Vector graphic export of each page"),
                ConversionOption(id="pdf_xlsx", name="PDF to Excel (XLSX)", category="pdf", input_format="pdf", output_format="xlsx", description="Extract tabular data from pages into Excel spreadsheet"),
                ConversionOption(id="pdf_pptx", name="PDF to PowerPoint (PPTX)", category="pdf", input_format="pdf", output_format="pptx", description="Convert pages into widescreen presentation slides"),
            ],
            utilities=[
                {"id": "merge", "name": "Merge PDFs", "description": "Combine multiple PDF documents into one"},
                {"id": "split", "name": "Split PDF", "description": "Extract individual pages or page ranges"},
                {"id": "compress", "name": "Compress PDF", "description": "Reduce file size via stream deflation"},
                {"id": "rotate", "name": "Rotate PDF", "description": "Rotate pages by 90, 180, or 270 degrees"},
                {"id": "watermark", "name": "Add Watermark", "description": "Stamp diagonal text watermark on every page"},
                {"id": "page_numbers", "name": "Add Page Numbers", "description": "Insert customizable page number footers"},
                {"id": "password_protect", "name": "Password Protect", "description": "Encrypt PDF with AES-256 password"},
                {"id": "remove_password", "name": "Remove Password", "description": "Unlock password-protected PDF"},
                {"id": "extract_images", "name": "Extract Images", "description": "Extract all embedded images to a ZIP archive"},
                {"id": "extract_text", "name": "Extract Text", "description": "Save all extracted text into a TXT file"},
                {"id": "metadata", "name": "Metadata Editor", "description": "View and modify document metadata (title, author)"},
            ]
        ),
        "word": CategoryConversions(
            category_id="word",
            name="Word Documents",
            description="Process and convert Microsoft Word, OpenDocument, and Rich Text files",
            formats=["docx", "doc", "odt", "rtf"],
            conversions=[
                ConversionOption(id="docx_pdf", name="DOCX to PDF", category="word", input_format="docx", output_format="pdf", description="Convert Word document to PDF format", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="docx_txt", name="DOCX to Text (TXT)", category="word", input_format="docx", output_format="txt", description="Extract clean text from Word documents"),
                ConversionOption(id="docx_html", name="DOCX to HTML", category="word", input_format="docx", output_format="html", description="Clean semantic HTML export from Word"),
                ConversionOption(id="docx_odt", name="DOCX to OpenDocument (ODT)", category="word", input_format="docx", output_format="odt", description="Export to open office standard", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="docx_rtf", name="DOCX to Rich Text (RTF)", category="word", input_format="docx", output_format="rtf", description="Export to RTF format", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="odt_docx", name="ODT to Word (DOCX)", category="word", input_format="odt", output_format="docx", description="Convert OpenDocument to Word", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="rtf_docx", name="RTF to Word (DOCX)", category="word", input_format="rtf", output_format="docx", description="Convert Rich Text to Word"),
                ConversionOption(id="doc_docx", name="Legacy DOC to DOCX", category="word", input_format="doc", output_format="docx", description="Upgrade legacy Word 97-2003 to DOCX", requires_libreoffice=True, is_available=has_lo),
            ]
        ),
        "spreadsheets": CategoryConversions(
            category_id="spreadsheets",
            name="Spreadsheets",
            description="Process Excel, CSV, ODS, and TSV spreadsheets locally",
            formats=["xlsx", "xls", "csv", "ods", "tsv"],
            conversions=[
                ConversionOption(id="xlsx_pdf", name="XLSX to PDF", category="spreadsheets", input_format="xlsx", output_format="pdf", description="Export spreadsheet layout or tables to PDF"),
                ConversionOption(id="xlsx_csv", name="XLSX to CSV", category="spreadsheets", input_format="xlsx", output_format="csv", description="Export active sheet to CSV comma separated"),
                ConversionOption(id="xlsx_html", name="XLSX to HTML", category="spreadsheets", input_format="xlsx", output_format="html", description="Export spreadsheet to styled HTML table"),
                ConversionOption(id="xlsx_ods", name="XLSX to ODS", category="spreadsheets", input_format="xlsx", output_format="ods", description="Convert Excel workbook to OpenDocument sheet"),
                ConversionOption(id="xls_xlsx", name="XLS to XLSX", category="spreadsheets", input_format="xls", output_format="xlsx", description="Convert legacy Excel 97-2003 to XLSX"),
                ConversionOption(id="csv_xlsx", name="CSV to Excel (XLSX)", category="spreadsheets", input_format="csv", output_format="xlsx", description="Convert CSV data into Excel workbook"),
                ConversionOption(id="csv_pdf", name="CSV to PDF", category="spreadsheets", input_format="csv", output_format="pdf", description="Render CSV data table to formatted PDF"),
                ConversionOption(id="ods_xlsx", name="ODS to Excel (XLSX)", category="spreadsheets", input_format="ods", output_format="xlsx", description="Convert OpenDocument spreadsheet to Excel"),
                ConversionOption(id="tsv_xlsx", name="TSV to Excel (XLSX)", category="spreadsheets", input_format="tsv", output_format="xlsx", description="Convert tab-separated values to Excel"),
            ],
            utilities=[
                {"id": "preview", "name": "Spreadsheet Preview", "description": "Preview sheets, columns, and rows directly in the browser"},
                {"id": "split_sheets", "name": "Split Sheets", "description": "Export each sheet into an individual workbook, downloaded as ZIP"},
                {"id": "merge_sheets", "name": "Merge Spreadsheets", "description": "Combine multiple files into one multi-sheet workbook"},
            ]
        ),
        "presentations": CategoryConversions(
            category_id="presentations",
            name="Presentations",
            description="Convert PowerPoint (PPTX/PPT) and OpenDocument presentations",
            formats=["pptx", "ppt", "odp"],
            conversions=[
                ConversionOption(id="pptx_pdf", name="PPTX to PDF", category="presentations", input_format="pptx", output_format="pdf", description="Export slides to PDF presentation", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="pptx_odp", name="PPTX to ODP", category="presentations", input_format="pptx", output_format="odp", description="Convert to OpenDocument presentation", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="odp_pptx", name="ODP to PPTX", category="presentations", input_format="odp", output_format="pptx", description="Convert to PowerPoint PPTX", requires_libreoffice=True, is_available=has_lo),
                ConversionOption(id="ppt_pptx", name="Legacy PPT to PPTX", category="presentations", input_format="ppt", output_format="pptx", description="Upgrade legacy PowerPoint to PPTX", requires_libreoffice=True, is_available=has_lo),
            ]
        ),
        "images": CategoryConversions(
            category_id="images",
            name="Images",
            description="High-fidelity local image processing, format conversion, and optimization",
            formats=["jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif", "svg", "ico"],
            conversions=[
                ConversionOption(id="jpg_png", name="JPG to PNG", category="images", input_format="jpg", output_format="png", description="Convert lossy JPEG to lossless PNG"),
                ConversionOption(id="png_jpg", name="PNG to JPG", category="images", input_format="png", output_format="jpg", description="Convert PNG to compressed JPEG with background"),
                ConversionOption(id="jpg_webp", name="JPG to WebP", category="images", input_format="jpg", output_format="webp", description="Convert JPG to modern web-optimized WebP"),
                ConversionOption(id="png_webp", name="PNG to WebP", category="images", input_format="png", output_format="webp", description="Convert PNG to high-efficiency WebP"),
                ConversionOption(id="webp_png", name="WebP to PNG", category="images", input_format="webp", output_format="png", description="Convert WebP to PNG"),
                ConversionOption(id="webp_jpg", name="WebP to JPG", category="images", input_format="webp", output_format="jpg", description="Convert WebP to JPG"),
                ConversionOption(id="tiff_png", name="TIFF to PNG", category="images", input_format="tiff", output_format="png", description="Convert TIFF to PNG"),
                ConversionOption(id="bmp_png", name="BMP to PNG", category="images", input_format="bmp", output_format="png", description="Convert uncompressed BMP to PNG"),
                ConversionOption(id="svg_png", name="SVG to PNG", category="images", input_format="svg", output_format="png", description="Rasterize vector SVG to crisp PNG"),
                ConversionOption(id="gif_png", name="GIF to PNG", category="images", input_format="gif", output_format="png", description="Extract first frame of GIF to PNG"),
                ConversionOption(id="img_pdf", name="Image to PDF", category="images", input_format="png", output_format="pdf", description="Convert image into PDF document"),
                ConversionOption(id="img_ico", name="Image to ICO Favicon", category="images", input_format="png", output_format="ico", description="Create multi-resolution ICO icon"),
            ],
            utilities=[
                {"id": "resize", "name": "Resize Image", "description": "Adjust width, height, or percentage scale"},
                {"id": "compress", "name": "Compress Image", "description": "Optimize image quality slider (1-100)"},
                {"id": "rotate", "name": "Rotate Image", "description": "Rotate image by specified angle"},
                {"id": "crop", "name": "Crop Image", "description": "Crop image to specific coordinates"},
                {"id": "strip_metadata", "name": "Remove EXIF Metadata", "description": "Strip location and camera metadata for privacy"},
                {"id": "multi_to_pdf", "name": "Multiple Images to Single PDF", "description": "Combine multiple photos into one PDF album"},
            ]
        ),
        "text": CategoryConversions(
            category_id="text",
            name="Text & Markdown",
            description="Process text files, Markdown documentation, and HTML markup",
            formats=["txt", "md", "html", "htm", "rtf"],
            conversions=[
                ConversionOption(id="txt_pdf", name="TXT to PDF", category="text", input_format="txt", output_format="pdf", description="Render plain text into formatted PDF"),
                ConversionOption(id="txt_docx", name="TXT to Word (DOCX)", category="text", input_format="txt", output_format="docx", description="Wrap text lines into Word document"),
                ConversionOption(id="md_html", name="Markdown to HTML", category="text", input_format="md", output_format="html", description="Compile markdown syntax into clean HTML"),
                ConversionOption(id="md_pdf", name="Markdown to PDF", category="text", input_format="md", output_format="pdf", description="Compile markdown into formatted PDF document"),
                ConversionOption(id="md_docx", name="Markdown to Word (DOCX)", category="text", input_format="md", output_format="docx", description="Convert markdown headings and lists into DOCX"),
                ConversionOption(id="html_pdf", name="HTML to PDF", category="text", input_format="html", output_format="pdf", description="Convert HTML markup into PDF"),
                ConversionOption(id="html_docx", name="HTML to Word (DOCX)", category="text", input_format="html", output_format="docx", description="Convert HTML structure to Word document"),
                ConversionOption(id="html_txt", name="HTML to Text (TXT)", category="text", input_format="html", output_format="txt", description="Strip HTML tags and extract readable text"),
            ]
        ),
        "ebook": CategoryConversions(
            category_id="ebook",
            name="Ebook Formats",
            description="Convert electronic book formats (.epub)",
            formats=["epub"],
            conversions=[
                ConversionOption(id="epub_pdf", name="EPUB to PDF", category="ebook", input_format="epub", output_format="pdf", description="Convert EPUB book to PDF", limitations="Text and chapter layouts preserved; complex custom reflowable fonts may differ."),
                ConversionOption(id="epub_txt", name="EPUB to Text (TXT)", category="ebook", input_format="epub", output_format="txt", description="Extract complete book text to plain text file"),
                ConversionOption(id="epub_html", name="EPUB to HTML", category="ebook", input_format="epub", output_format="html", description="Consolidate all book chapters into readable HTML"),
            ]
        ),
        "archive": CategoryConversions(
            category_id="archive",
            name="Archive & Compression",
            description="Safe file decompression and compression utilities",
            formats=["zip"],
            conversions=[
                ConversionOption(id="zip_extract", name="Extract ZIP", category="archive", input_format="zip", output_format="extract", description="Safely unpack ZIP archive with path traversal protection"),
            ]
        ),
        "ocr": CategoryConversions(
            category_id="ocr",
            name="Local OCR",
            description="Offline optical character recognition using local Tesseract engine",
            formats=["pdf", "jpg", "jpeg", "png", "tiff"],
            conversions=[
                ConversionOption(id="ocr_img_pdf", name="Image to Searchable PDF", category="ocr", input_format="png", output_format="pdf", description="Generate searchable PDF with embedded text layer", requires_tesseract=True, is_available=has_tess),
                ConversionOption(id="ocr_img_txt", name="Image to Text (TXT)", category="ocr", input_format="png", output_format="txt", description="Extract text characters from photo/scanned image", requires_tesseract=True, is_available=has_tess),
                ConversionOption(id="ocr_pdf_pdf", name="Scanned PDF to Searchable PDF", category="ocr", input_format="pdf", output_format="pdf", description="Add searchable text layer to scanned PDF", requires_tesseract=True, is_available=has_tess),
                ConversionOption(id="ocr_pdf_txt", name="Scanned PDF to Text (TXT)", category="ocr", input_format="pdf", output_format="txt", description="Extract text from scanned PDF pages", requires_tesseract=True, is_available=has_tess),
            ]
        )
    }

    supported_inputs = []
    for cat in categories.values():
        for fmt in cat.formats:
            if fmt not in supported_inputs:
                supported_inputs.append(fmt)

    return ConversionRegistryResponse(
        categories=categories,
        supported_inputs=supported_inputs,
        max_file_size_mb=settings.MAX_FILE_SIZE_MB,
        system_capabilities={
            "libreoffice": has_lo,
            "tesseract": has_tess,
            "ocr_tamil": "tam" in ocr_service.get_installed_languages() if has_tess else False,
            "poppler": True
        }
    )


def execute_conversion(
    input_path: Path,
    target_format: str,
    conversion_type: str,
    output_dir: Path,
    options: Optional[Dict[str, Any]] = None
) -> List[Path]:
    """
    Routes conversion request to appropriate service based on input file type and target.
    """
    ext = input_path.suffix.lower().lstrip(".")
    target = target_format.lower().lstrip(".")
    options = options or {}

    # OCR routing
    if conversion_type == "ocr":
        return ocr_service.convert(input_path, target, output_dir, options)

    # PDF routing
    if ext == "pdf":
        return pdf_service.convert(input_path, target, output_dir, options)

    # Word / Presentations routing
    if ext in ("docx", "doc", "odt", "rtf", "pptx", "ppt", "odp"):
        return office_service.convert(input_path, target, output_dir, options)

    # Spreadsheets routing
    if ext in ("xlsx", "xls", "csv", "ods", "tsv"):
        return spreadsheet_service.convert(input_path, target, output_dir, options)

    # Images routing
    if ext in ("jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif", "svg", "ico"):
        return image_service.convert(input_path, target, output_dir, options)

    # Text / Markdown / HTML routing
    if ext in ("txt", "md", "html", "htm"):
        return text_service.convert(input_path, target, output_dir, options)

    # Ebooks routing
    if ext == "epub":
        return ebook_service.convert(input_path, target, output_dir, options)

    # Archives routing
    if ext == "zip":
        return archive_service.convert(input_path, target, output_dir, options)

    raise ValueError(f"No converter found for extension .{ext} to .{target}")
