import io
import math
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF

# Compatibility shim for newer PyMuPDF versions with pdf2docx
if not hasattr(fitz.Rect, "get_area"):
    fitz.Rect.get_area = lambda self: abs(self.width * self.height)

from pdf2docx import Converter as Pdf2DocxConverter
import pdfplumber
import openpyxl
from pptx import Presentation
from pptx.util import Inches

from app.services.base_converter import BaseConverter
from app.utils.security import sanitize_filename


class PDFService(BaseConverter):
    @property
    def supported_inputs(self) -> List[str]:
        return ["pdf"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        return {
            "pdf": ["docx", "txt", "html", "png", "jpg", "jpeg", "svg", "xlsx", "pptx"]
        }

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        target = target_format.lower().lstrip(".")
        options = options or {}
        stem = input_path.stem

        if target == "docx":
            return self.pdf_to_docx(input_path, output_dir)
        elif target == "txt":
            return self.pdf_to_txt(input_path, output_dir)
        elif target == "html":
            return self.pdf_to_html(input_path, output_dir)
        elif target in ("png", "jpg", "jpeg"):
            dpi = int(options.get("dpi", 150))
            return self.pdf_to_images(input_path, output_dir, img_format=target, dpi=dpi)
        elif target == "svg":
            return self.pdf_to_svg(input_path, output_dir)
        elif target == "xlsx":
            return self.pdf_to_xlsx(input_path, output_dir)
        elif target == "pptx":
            return self.pdf_to_pptx(input_path, output_dir)
        else:
            raise ValueError(f"Unsupported target format for PDF: {target}")

    # ================= CONVERSIONS =================

    def pdf_to_docx(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        out_path = output_dir / f"{pdf_path.stem}.docx"
        cv = Pdf2DocxConverter(str(pdf_path))
        try:
            cv.convert(str(out_path), start=0, end=None)
        finally:
            cv.close()
        return [out_path]

    def pdf_to_txt(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        out_path = output_dir / f"{pdf_path.stem}.txt"
        doc = fitz.open(str(pdf_path))
        try:
            text_parts = []
            for i, page in enumerate(doc):
                text_parts.append(f"--- Page {i + 1} ---\n")
                text_parts.append(page.get_text())
                text_parts.append("\n\n")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("".join(text_parts))
        finally:
            doc.close()
        return [out_path]

    def pdf_to_html(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        out_path = output_dir / f"{pdf_path.stem}.html"
        doc = fitz.open(str(pdf_path))
        try:
            html_parts = [
                "<!DOCTYPE html>",
                "<html><head><meta charset='utf-8'><title>",
                f"{pdf_path.stem}",
                "</title><style>",
                "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; background: #f8fafc; color: #1e293b; }",
                ".pdf-page { background: #fff; padding: 2.5rem; margin-bottom: 2rem; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }",
                ".page-num { font-size: 0.8rem; color: #94a3b8; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; margin-bottom: 1rem; }",
                "</style></head><body>"
            ]
            for i, page in enumerate(doc):
                html_parts.append(f"<div class='pdf-page'><div class='page-num'>Page {i + 1}</div>")
                html_parts.append(page.get_text("html"))
                html_parts.append("</div>")
            html_parts.append("</body></html>")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(html_parts))
        finally:
            doc.close()
        return [out_path]

    def pdf_to_images(
        self,
        pdf_path: Path,
        output_dir: Path,
        img_format: str = "png",
        dpi: int = 150
    ) -> List[Path]:
        doc = fitz.open(str(pdf_path))
        generated = []
        fmt = "jpeg" if img_format in ("jpg", "jpeg") else "png"
        ext = "jpg" if img_format in ("jpg", "jpeg") else "png"
        
        try:
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix, alpha=(fmt == "png"))
                out_path = output_dir / f"{pdf_path.stem}_page_{i + 1}.{ext}"
                pix.save(str(out_path))
                generated.append(out_path)
        finally:
            doc.close()

        # If more than one page, create a bundled zip as well
        if len(generated) > 1:
            zip_path = output_dir / f"{pdf_path.stem}_images.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for img in generated:
                    zf.write(img, arcname=img.name)
            return [zip_path]

        return generated

    def pdf_to_svg(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        doc = fitz.open(str(pdf_path))
        generated = []
        try:
            for i, page in enumerate(doc):
                svg_data = page.get_svg_image()
                out_path = output_dir / f"{pdf_path.stem}_page_{i + 1}.svg"
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(svg_data)
                generated.append(out_path)
        finally:
            doc.close()

        if len(generated) > 1:
            zip_path = output_dir / f"{pdf_path.stem}_svg.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for svg in generated:
                    zf.write(svg, arcname=svg.name)
            return [zip_path]

        return generated

    def pdf_to_xlsx(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        """Extracts tables from PDF pages into an Excel spreadsheet workbook."""
        out_path = output_dir / f"{pdf_path.stem}.xlsx"
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        has_tables = False
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    # Fallback: extract text lines if no structured tables
                    text = page.extract_text()
                    if text:
                        ws = wb.create_sheet(title=f"Page {i + 1}")
                        for r_idx, line in enumerate(text.splitlines(), start=1):
                            ws.cell(row=r_idx, column=1, value=line)
                        has_tables = True
                    continue

                for t_idx, table in enumerate(tables):
                    has_tables = True
                    sheet_name = f"P{i + 1}_T{t_idx + 1}"[:31]
                    ws = wb.create_sheet(title=sheet_name)
                    for r_idx, row in enumerate(table, start=1):
                        for c_idx, cell in enumerate(row, start=1):
                            ws.cell(row=r_idx, column=c_idx, value=cell)

        if not has_tables:
            ws = wb.create_sheet(title="Extracted Content")
            ws.cell(row=1, column=1, value="No tables or text detected in PDF.")

        wb.save(str(out_path))
        return [out_path]

    def pdf_to_pptx(self, pdf_path: Path, output_dir: Path) -> List[Path]:
        """Converts each PDF page into a slide in PowerPoint Presentation."""
        out_path = output_dir / f"{pdf_path.stem}.pptx"
        prs = Presentation()
        # Set 16:9 widescreen or standard
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]  # completely blank slide

        doc = fitz.open(str(pdf_path))
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                slide = prs.slides.add_slide(blank_layout)
                slide.shapes.add_picture(
                    io.BytesIO(img_bytes),
                    Inches(0), Inches(0),
                    width=prs.slide_width,
                    height=prs.slide_height
                )
        finally:
            doc.close()

        prs.save(str(out_path))
        return [out_path]

    # ================= UTILITIES =================

    def merge_pdfs(self, pdf_paths: List[Path], output_dir: Path, out_filename: str = "merged.pdf") -> Path:
        out_path = output_dir / sanitize_filename(out_filename)
        merged = fitz.open()
        for p in pdf_paths:
            src = fitz.open(str(p))
            merged.insert_pdf(src)
            src.close()
        merged.save(str(out_path))
        merged.close()
        return out_path

    def split_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        pages: Optional[List[int]] = None,
        chunk_size: Optional[int] = None
    ) -> List[Path]:
        """Splits PDF. If pages specified, extracts those; if chunk_size specified, splits in chunks; otherwise splits each page."""
        doc = fitz.open(str(pdf_path))
        generated = []
        try:
            total_pages = len(doc)
            if pages is not None:
                out_pdf = fitz.open()
                valid_pages = [p for p in pages if 0 <= p < total_pages]
                if not valid_pages:
                    raise ValueError(f"No valid pages specified (Document has {total_pages} pages).")
                for p in valid_pages:
                    out_pdf.insert_pdf(doc, from_page=p, to_page=p)
                out_path = output_dir / f"{pdf_path.stem}_extracted.pdf"
                out_pdf.save(str(out_path))
                out_pdf.close()
                generated.append(out_path)
            elif chunk_size and chunk_size > 0:
                for chunk_idx, start in enumerate(range(0, total_pages, chunk_size), start=1):
                    end = min(start + chunk_size - 1, total_pages - 1)
                    out_pdf = fitz.open()
                    out_pdf.insert_pdf(doc, from_page=start, to_page=end)
                    chunk_file = output_dir / f"{pdf_path.stem}_part{chunk_idx}_p{start+1}-{end+1}.pdf"
                    out_pdf.save(str(chunk_file))
                    out_pdf.close()
                    generated.append(chunk_file)
            else:
                for i in range(total_pages):
                    out_pdf = fitz.open()
                    out_pdf.insert_pdf(doc, from_page=i, to_page=i)
                    p_path = output_dir / f"{pdf_path.stem}_page_{i + 1}.pdf"
                    out_pdf.save(str(p_path))
                    out_pdf.close()
                    generated.append(p_path)
        finally:
            doc.close()

        if len(generated) > 1:
            zip_path = output_dir / f"{pdf_path.stem}_split.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in generated:
                    zf.write(f, arcname=f.name)
            return [zip_path]

        return generated

    def compress_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        quality: int = 65,
        dpi: Optional[int] = 150,
        grayscale: bool = False,
        strip_metadata: bool = True
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_compressed.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            # Recompress and downsample embedded images
            if quality < 100 or dpi or grayscale:
                target_dpi = dpi or 150
                threshold_dpi = max(target_dpi + 1, 73)
                try:
                    doc.rewrite_images(
                        dpi_threshold=threshold_dpi,
                        dpi_target=target_dpi,
                        quality=quality,
                        set_to_gray=grayscale
                    )
                except Exception as e:
                    logger.warning("Image rewriting skipped: %s", e)

            if strip_metadata:
                try:
                    doc.set_metadata({})
                except Exception:
                    pass

            doc.save(
                str(out_path),
                garbage=4,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                clean=True
            )
        finally:
            doc.close()
        return out_path

    def rotate_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        angle: int = 90,
        pages: Optional[List[int]] = None,
        scope: str = "all"
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_rotated.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            total = len(doc)
            if scope == "odd":
                target_indices = [i for i in range(total) if i % 2 == 0]
            elif scope == "even":
                target_indices = [i for i in range(total) if i % 2 != 0]
            elif pages is not None and len(pages) > 0:
                target_indices = pages
            else:
                target_indices = list(range(total))

            for i in target_indices:
                if 0 <= i < total:
                    page = doc[i]
                    page.set_rotation((page.rotation + angle) % 360)
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path

    def reorder_pages(self, pdf_path: Path, output_dir: Path, new_order: List[int]) -> Path:
        """new_order is 0-indexed list of page indices."""
        out_path = output_dir / f"{pdf_path.stem}_reordered.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            doc.select(new_order)
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path

    def delete_pages(self, pdf_path: Path, output_dir: Path, pages_to_delete: List[int]) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_deleted_pages.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            valid_pages = [p for p in pages_to_delete if 0 <= p < len(doc)]
            if not valid_pages:
                raise ValueError("No valid pages to delete.")
            doc.delete_pages(valid_pages)
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path

    def add_watermark(
        self,
        pdf_path: Path,
        output_dir: Path,
        watermark_text: str = "CONFIDENTIAL",
        opacity: float = 0.3,
        fontsize: int = 40,
        color_name: str = "gray",
        angle: int = 45,
        on_top: bool = True
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_watermarked.pdf"
        color_map = {
            "gray": (0.6, 0.6, 0.6),
            "red": (0.85, 0.15, 0.15),
            "blue": (0.15, 0.35, 0.85),
            "green": (0.15, 0.65, 0.25),
            "black": (0.05, 0.05, 0.05),
        }
        color = color_map.get(str(color_name).lower(), (0.6, 0.6, 0.6))
        doc = fitz.open(str(pdf_path))
        try:
            for page in doc:
                rect = page.rect
                center = fitz.Point(rect.width / 2, rect.height / 2)
                morph = (center, fitz.Matrix(angle)) if angle != 0 else None
                page.insert_text(
                    center,
                    watermark_text,
                    fontsize=fontsize,
                    morph=morph,
                    color=color,
                    fill_opacity=opacity,
                    overlay=on_top
                )
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path

    def add_page_numbers(
        self,
        pdf_path: Path,
        output_dir: Path,
        format_pattern: str = "Page {page} of {total}",
        position: str = "bottom_center",
        start_page: int = 1,
        fontsize: int = 10,
        color: Tuple[float, float, float] = (0.3, 0.3, 0.3)
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_numbered.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            total = len(doc)
            for i, page in enumerate(doc):
                num_text = format_pattern.format(page=i + start_page, total=total + start_page - 1)
                rect = page.rect
                if position == "bottom_center":
                    point = fitz.Point(rect.width / 2 - 35, rect.height - 25)
                elif position == "bottom_right":
                    point = fitz.Point(rect.width - 100, rect.height - 25)
                elif position == "bottom_left":
                    point = fitz.Point(40, rect.height - 25)
                elif position == "top_right":
                    point = fitz.Point(rect.width - 100, 35)
                else:
                    point = fitz.Point(rect.width / 2 - 35, 35)

                page.insert_text(
                    point,
                    num_text,
                    fontsize=fontsize,
                    color=color
                )
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path

    def password_protect(
        self,
        pdf_path: Path,
        output_dir: Path,
        user_password: str,
        owner_password: Optional[str] = None,
        allow_print: bool = True,
        allow_copy: bool = False
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_protected.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            permissions = 0
            if allow_print:
                permissions |= fitz.PDF_PERM_PRINT
            if allow_copy:
                permissions |= fitz.PDF_PERM_COPY

            doc.save(
                str(out_path),
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw=user_password,
                owner_pw=owner_password or user_password,
                permissions=permissions if permissions > 0 else None
            )
        finally:
            doc.close()
        return out_path

    def remove_password(
        self,
        pdf_path: Path,
        output_dir: Path,
        password: str
    ) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_unprotected.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            if doc.is_encrypted:
                auth = doc.authenticate(password)
                if not auth:
                    raise ValueError("Incorrect password for protected PDF.")
            doc.save(str(out_path), encryption=fitz.PDF_ENCRYPT_NONE)
        finally:
            doc.close()
        return out_path

    def extract_images(
        self,
        pdf_path: Path,
        output_dir: Path,
        min_dimension: int = 50,
        output_format: str = "original"
    ) -> Path:
        """Extracts all raster images from PDF and saves them in a ZIP archive."""
        out_zip = output_dir / f"{pdf_path.stem}_extracted_images.zip"
        doc = fitz.open(str(pdf_path))
        extracted_count = 0
        try:
            with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for page_idx, page in enumerate(doc):
                    image_list = page.get_images(full=True)
                    for img_idx, img in enumerate(image_list):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)
                        if width < min_dimension and height < min_dimension:
                            continue

                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]

                        if output_format in ("png", "jpg", "jpeg") and image_ext != output_format:
                            try:
                                pil_img = Image.open(io.BytesIO(image_bytes))
                                b = io.BytesIO()
                                save_fmt = "JPEG" if output_format in ("jpg", "jpeg") else "PNG"
                                if save_fmt == "JPEG" and pil_img.mode in ("RGBA", "P"):
                                    pil_img = pil_img.convert("RGB")
                                pil_img.save(b, format=save_fmt)
                                image_bytes = b.getvalue()
                                image_ext = "jpg" if save_fmt == "JPEG" else "png"
                            except Exception:
                                pass

                        img_name = f"p{page_idx + 1}_img{img_idx + 1}.{image_ext}"
                        zf.writestr(img_name, image_bytes)
                        extracted_count += 1
                        
            if extracted_count == 0:
                with zipfile.ZipFile(out_zip, "a") as zf:
                    zf.writestr("info.txt", "No embedded images matching criteria found in this PDF.")
        finally:
            doc.close()
        return out_zip

    def get_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        doc = fitz.open(str(pdf_path))
        try:
            meta = doc.metadata or {}
            return {
                "title": meta.get("title") or "",
                "author": meta.get("author") or "",
                "subject": meta.get("subject") or "",
                "keywords": meta.get("keywords") or "",
                "creator": meta.get("creator") or "",
                "producer": meta.get("producer") or "",
                "page_count": len(doc),
                "is_encrypted": doc.is_encrypted
            }
        finally:
            doc.close()

    def update_metadata(self, pdf_path: Path, output_dir: Path, new_meta: Dict[str, str]) -> Path:
        out_path = output_dir / f"{pdf_path.stem}_meta_updated.pdf"
        doc = fitz.open(str(pdf_path))
        try:
            doc.set_metadata({
                "title": new_meta.get("title", doc.metadata.get("title", "")),
                "author": new_meta.get("author", doc.metadata.get("author", "")),
                "subject": new_meta.get("subject", doc.metadata.get("subject", "")),
                "keywords": new_meta.get("keywords", doc.metadata.get("keywords", "")),
            })
            doc.save(str(out_path))
        finally:
            doc.close()
        return out_path


pdf_service = PDFService()
