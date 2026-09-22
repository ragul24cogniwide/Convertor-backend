import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from xhtml2pdf import pisa

from app.services.base_converter import BaseConverter


class EbookService(BaseConverter):
    @property
    def supported_inputs(self) -> List[str]:
        return ["epub"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        return {
            "epub": ["pdf", "txt", "html"]
        }

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        target = target_format.lower().lstrip(".")
        stem = input_path.stem
        out_path = output_dir / f"{stem}.{target}"

        book = epub.read_epub(str(input_path))
        html_chapters = []
        text_chapters = []

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                body = soup.find("body")
                if body:
                    html_chapters.append(str(body))
                    text_chapters.append(body.get_text(separator="\n"))
                else:
                    html_chapters.append(str(soup))
                    text_chapters.append(soup.get_text(separator="\n"))

        if target == "txt":
            full_text = "\n\n=== NEXT CHAPTER ===\n\n".join(text_chapters)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            return [out_path]

        combined_html = (
            "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
            f"<title>{stem}</title>"
            "<style>"
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', serif; max-width: 800px; margin: 2rem auto; padding: 0 1.5rem; line-height: 1.8; color: #1e293b; background: #fff; }"
            "img { max-width: 100%; height: auto; }"
            "h1, h2, h3 { color: #0f172a; margin-top: 2rem; }"
            ".chapter-divider { border-top: 1px solid #e2e8f0; margin: 3rem 0; }"
            "</style></head><body>"
            + "<div class='chapter-divider'></div>".join(html_chapters)
            + "</body></html>"
        )

        if target == "html":
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(combined_html)
            return [out_path]

        elif target == "pdf":
            with open(out_path, "wb") as f:
                pisa_status = pisa.CreatePDF(combined_html, dest=f)
            if pisa_status.err:
                raise RuntimeError("Failed to generate PDF from EPUB content.")
            return [out_path]

        raise ValueError(f"Unsupported EPUB target: {target}")


ebook_service = EbookService()
