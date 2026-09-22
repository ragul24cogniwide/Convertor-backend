import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import docx
import mammoth

from app.services.base_converter import BaseConverter
from app.utils.security import safe_subprocess_run


def find_libreoffice_binary() -> Optional[str]:
    """Finds the LibreOffice headless executable path on Linux, macOS, or Windows."""
    # Standard PATH names
    for name in ["soffice", "libreoffice"]:
        path = shutil.which(name)
        if path:
            return path

    # macOS standard application paths
    macos_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/local/bin/soffice",
        "/opt/homebrew/bin/soffice"
    ]
    for p in macos_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # Linux standard paths
    linux_paths = [
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/lib/libreoffice/program/soffice"
    ]
    for p in linux_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    return None


class OfficeService(BaseConverter):
    def __init__(self):
        self.soffice_bin = find_libreoffice_binary()

    @property
    def has_libreoffice(self) -> bool:
        return self.soffice_bin is not None

    def get_version(self) -> Optional[str]:
        if not self.soffice_bin:
            return None
        try:
            res = safe_subprocess_run([self.soffice_bin, "--version"], timeout=5)
            return res.stdout.strip() or res.stderr.strip()
        except Exception:
            return "Installed"

    @property
    def supported_inputs(self) -> List[str]:
        return ["docx", "doc", "odt", "rtf", "pptx", "ppt", "odp"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        outputs = {
            "docx": ["txt", "html", "pdf", "odt", "rtf"],
            "odt": ["docx", "pdf", "txt"],
            "rtf": ["docx", "txt", "pdf"],
            "doc": ["docx", "pdf", "txt"],
            "pptx": ["pdf", "images", "odp"],
            "ppt": ["pptx", "pdf"],
            "odp": ["pptx", "pdf"],
        }
        return outputs

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        ext = input_path.suffix.lower().lstrip(".")
        target = target_format.lower().lstrip(".")

        # Pure Python DOCX conversions
        if ext == "docx" and target == "txt":
            return self.docx_to_txt(input_path, output_dir)
        elif ext == "docx" and target == "html":
            return self.docx_to_html(input_path, output_dir)

        # LibreOffice headless conversions
        return self.convert_via_libreoffice(input_path, target, output_dir)

    def docx_to_txt(self, docx_path: Path, output_dir: Path) -> List[Path]:
        out_path = output_dir / f"{docx_path.stem}.txt"
        doc = docx.Document(str(docx_path))
        lines = []
        for p in doc.paragraphs:
            lines.append(p.text)
        for table in doc.tables:
            lines.append("\n[Table]")
            for row in table.rows:
                lines.append("\t".join(cell.text.strip() for cell in row.cells))
            lines.append("")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return [out_path]

    def docx_to_html(self, docx_path: Path, output_dir: Path) -> List[Path]:
        out_path = output_dir / f"{docx_path.stem}.html"
        with open(docx_path, "rb") as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html_content = result.value
            
        full_html = (
            "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
            f"<title>{docx_path.stem}</title>"
            "<style>body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
            "margin: 2rem auto; max-width: 800px; padding: 0 1rem; line-height: 1.6; color: #1e293b; }</style>"
            f"</head><body>{html_content}</body></html>"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        return [out_path]

    def convert_via_libreoffice(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path
    ) -> List[Path]:
        if not self.soffice_bin:
            raise RuntimeError(
                f"LibreOffice is required to convert .{input_path.suffix.lstrip('.')} to .{target_format}. "
                "Please install LibreOffice locally or use the Docker environment."
            )

        cmd = [
            self.soffice_bin,
            "--headless",
            "--convert-to",
            target_format,
            "--outdir",
            str(output_dir),
            str(input_path)
        ]

        res = safe_subprocess_run(cmd, timeout=120)
        if res.returncode != 0:
            err_detail = res.stderr.strip() or res.stdout.strip() or "Unknown error"
            raise RuntimeError(f"LibreOffice conversion failed: {err_detail}")

        # The output file name will be input_path.stem + target_format
        expected_out = output_dir / f"{input_path.stem}.{target_format}"
        if not expected_out.exists():
            # Check if any matching file was created in output_dir
            candidates = list(output_dir.glob(f"*.{target_format}"))
            if candidates:
                return candidates
            raise FileNotFoundError(f"LibreOffice succeeded but target file was not generated: {expected_out.name}")

        return [expected_out]


office_service = OfficeService()
