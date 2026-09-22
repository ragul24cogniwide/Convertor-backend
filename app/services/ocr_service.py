import io
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import fitz  # PyMuPDF
import pytesseract

from app.services.base_converter import BaseConverter


def find_tesseract_binary() -> Optional[str]:
    for name in ["tesseract"]:
        path = shutil.which(name)
        if path:
            return path
    macos_paths = ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]
    for p in macos_paths:
        if Path(p).exists():
            return p
    return None


class OCRService(BaseConverter):
    def __init__(self):
        self.tesseract_bin = find_tesseract_binary()
        if self.tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_bin

    @property
    def is_available(self) -> bool:
        return self.tesseract_bin is not None

    def get_version(self) -> Optional[str]:
        if not self.is_available:
            return None
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:
            return "Installed"

    def get_installed_languages(self) -> List[str]:
        if not self.is_available:
            return ["eng"]
        try:
            langs = pytesseract.get_languages()
            return langs if langs else ["eng"]
        except Exception:
            return ["eng"]

    @property
    def supported_inputs(self) -> List[str]:
        return ["pdf", "jpg", "jpeg", "png", "tiff", "tif"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        return {
            "pdf": ["pdf", "txt"],
            "jpg": ["pdf", "txt"],
            "jpeg": ["pdf", "txt"],
            "png": ["pdf", "txt"],
            "tiff": ["pdf", "txt"],
            "tif": ["pdf", "txt"]
        }

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        if not self.is_available:
            raise RuntimeError(
                "Tesseract OCR is not installed on this server. "
                "Please install tesseract-ocr (and language packs) or run via Docker."
            )

        options = options or {}
        lang = options.get("language", "eng")
        # Tamil check: allow 'tam' or 'eng+tam'
        ext = input_path.suffix.lower().lstrip(".")
        target = target_format.lower().lstrip(".")
        stem = input_path.stem

        out_path = output_dir / f"{stem}_ocr.{target}"

        if ext == "pdf":
            return self._ocr_pdf(input_path, target, out_path, lang)
        else:
            return self._ocr_image(input_path, target, out_path, lang)

    def _ocr_image(self, img_path: Path, target: str, out_path: Path, lang: str) -> List[Path]:
        with Image.open(str(img_path)) as img:
            if target == "txt":
                text = pytesseract.image_to_string(img, lang=lang)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
            elif target == "pdf":
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang=lang)
                with open(out_path, "wb") as f:
                    f.write(pdf_bytes)
            else:
                raise ValueError(f"Unsupported OCR target format: {target}")
        return [out_path]

    def _ocr_pdf(self, pdf_path: Path, target: str, out_path: Path, lang: str) -> List[Path]:
        doc = fitz.open(str(pdf_path))
        try:
            if target == "txt":
                full_text = []
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang=lang)
                    full_text.append(f"--- Page {i + 1} ---\n{text}\n")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(full_text))
            elif target == "pdf":
                # Create a new searchable PDF document combining OCR pages
                merged_pdf = fitz.open()
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang=lang)
                    ocr_page_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    merged_pdf.insert_pdf(ocr_page_doc)
                    ocr_page_doc.close()
                merged_pdf.save(str(out_path))
                merged_pdf.close()
            else:
                raise ValueError(f"Unsupported OCR target format: {target}")
        finally:
            doc.close()
        return [out_path]


ocr_service = OCRService()
