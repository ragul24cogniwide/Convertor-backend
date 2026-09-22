import os
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.base_converter import BaseConverter
from app.utils.security import sanitize_filename, validate_zip_archive, prevent_path_traversal


class ArchiveService(BaseConverter):
    @property
    def supported_inputs(self) -> List[str]:
        return ["zip"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        return {
            "zip": ["extract"]
        }

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        return self.safe_extract_zip(input_path, output_dir)

    def safe_extract_zip(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """
        Extracts ZIP contents with strict protection against:
        - Zip Slip (path traversal "../")
        - Absolute paths ("/etc/passwd")
        - Decompression bombs
        """
        validate_zip_archive(zip_path)
        extracted_files = []

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                # Skip directory entries
                if member.is_dir():
                    continue

                # Clean entry name
                parts = Path(member.filename).parts
                clean_parts = [sanitize_filename(p) for p in parts if p not in ("..", ".", "/", "\\")]
                if not clean_parts:
                    continue
                    
                target_file_path = output_dir.joinpath(*clean_parts)
                
                # Check path traversal
                prevent_path_traversal(output_dir, target_file_path)
                
                # Create parent dirs safely
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with zf.open(member) as source, open(target_file_path, "wb") as target:
                    target.write(source.read())
                    
                extracted_files.append(target_file_path)

        return extracted_files

    def create_zip(self, file_paths: List[Path], output_zip: Path) -> Path:
        """Packages a list of files into a ZIP archive."""
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in file_paths:
                if f.exists() and f.is_file():
                    zf.write(f, arcname=f.name)
        return output_zip


archive_service = ArchiveService()
