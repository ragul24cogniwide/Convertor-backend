import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageOps
import fitz  # PyMuPDF can also parse SVG and write raster images losslessly

from app.services.base_converter import BaseConverter


class ImageService(BaseConverter):
    @property
    def supported_inputs(self) -> List[str]:
        return ["jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif", "svg", "ico"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        raster_outputs = ["png", "jpg", "jpeg", "webp", "pdf", "ico", "bmp", "tiff"]
        return {
            "jpg": [o for o in raster_outputs if o not in ("jpg", "jpeg")],
            "jpeg": [o for o in raster_outputs if o not in ("jpg", "jpeg")],
            "png": [o for o in raster_outputs if o != "png"],
            "webp": [o for o in raster_outputs if o != "webp"],
            "gif": ["png", "jpg", "webp", "pdf"],
            "bmp": ["png", "jpg", "webp", "pdf"],
            "tiff": ["png", "jpg", "webp", "pdf"],
            "tif": ["png", "jpg", "webp", "pdf"],
            "svg": ["png", "jpg", "webp", "pdf"],
            "ico": ["png", "jpg", "webp"],
        }

    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        ext = input_path.suffix.lower().lstrip(".")
        target = target_format.lower().lstrip(".")
        options = options or {}
        stem = input_path.stem
        out_path = output_dir / f"{stem}.{target}"

        # SVG input handling
        if ext == "svg":
            return self._convert_svg(input_path, target, out_path, options)

        # Standard raster conversions using Pillow
        with Image.open(str(input_path)) as img:
            # Handle EXIF rotation orientation automatically
            img = ImageOps.exif_transpose(img)

            # Apply utilities/transformations if passed in options
            img = self._apply_transforms(img, options)

            # Format specific conversions
            if target in ("jpg", "jpeg"):
                if img.mode in ("RGBA", "LA", "P"):
                    # Create white background for alpha channels
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                else:
                    img = img.convert("RGB")
                quality = int(options.get("quality", 90))
                img.save(str(out_path), "JPEG", quality=quality, optimize=True)

            elif target == "png":
                img.save(str(out_path), "PNG", optimize=True)

            elif target == "webp":
                quality = int(options.get("quality", 90))
                img.save(str(out_path), "WEBP", quality=quality)

            elif target == "ico":
                sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
                img.save(str(out_path), format="ICO", sizes=sizes)

            elif target == "bmp":
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(str(out_path), "BMP")

            elif target in ("tiff", "tif"):
                img.save(str(out_path), "TIFF")

            elif target == "pdf":
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(str(out_path), "PDF", resolution=float(options.get("dpi", 100.0)))

            else:
                raise ValueError(f"Unsupported image target format: {target}")

        return [out_path]

    def _convert_svg(self, svg_path: Path, target: str, out_path: Path, options: Dict[str, Any]) -> List[Path]:
        """Converts SVG to PNG/JPG/PDF using PyMuPDF vector renderer."""
        svg_content = svg_path.read_bytes()
        # Open SVG as PDF document stream in PyMuPDF
        doc = fitz.open(stream=svg_content, filetype="svg")
        try:
            page = doc[0]
            dpi = int(options.get("dpi", 150))
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=(target == "png"))
            
            if target in ("png", "webp", "jpg", "jpeg"):
                # Save as PNG first
                png_bytes = pix.tobytes("png")
                with Image.open(io.BytesIO(png_bytes)) as pil_img:
                    if target in ("jpg", "jpeg"):
                        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                        bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == "RGBA" else None)
                        bg.save(str(out_path), "JPEG", quality=90)
                    elif target == "webp":
                        pil_img.save(str(out_path), "WEBP", quality=90)
                    else:
                        pil_img.save(str(out_path), "PNG")
            elif target == "pdf":
                pdf_bytes = doc.convert_to_pdf()
                with open(out_path, "wb") as f:
                    f.write(pdf_bytes)
        finally:
            doc.close()
        return [out_path]

    def _apply_transforms(self, img: Image.Image, options: Dict[str, Any]) -> Image.Image:
        # Resize
        if "width" in options or "height" in options:
            w = options.get("width")
            h = options.get("height")
            orig_w, orig_h = img.size
            
            if w and not h:
                h = int(orig_h * (w / orig_w))
            elif h and not w:
                w = int(orig_w * (h / orig_h))
                
            if w and h:
                img = img.resize((int(w), int(h)), Image.Resampling.LANCZOS)

        # Scale percentage
        if "scale_percent" in options:
            pct = float(options["scale_percent"]) / 100.0
            if pct > 0:
                new_w = max(1, int(img.width * pct))
                new_h = max(1, int(img.height * pct))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Rotation
        if "rotate_angle" in options:
            angle = float(options["rotate_angle"])
            if angle != 0:
                img = img.rotate(-angle, expand=True)

        # Crop (box: [left, top, right, bottom])
        if "crop_box" in options and isinstance(options["crop_box"], (list, tuple)) and len(options["crop_box"]) == 4:
            img = img.crop(options["crop_box"])

        # Strip metadata
        if options.get("strip_metadata", False):
            # Create a clean copy devoid of exif or color profiles
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
            img = clean_img

        return img

    def images_to_pdf(self, image_paths: List[Path], output_dir: Path, out_filename: str = "combined.pdf") -> Path:
        """Combines multiple images into a single PDF document."""
        out_path = output_dir / out_filename
        pil_images = []
        for p in image_paths:
            img = Image.open(str(p))
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            pil_images.append(img)

        if not pil_images:
            raise ValueError("No images provided to combine into PDF.")

        first = pil_images[0]
        rest = pil_images[1:]
        first.save(str(out_path), "PDF", resolution=100.0, save_all=True, append_images=rest)
        
        for img in pil_images:
            img.close()
            
        return out_path


image_service = ImageService()
