import csv
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.services.base_converter import BaseConverter
from app.services.office_service import office_service


class SpreadsheetService(BaseConverter):
    @property
    def supported_inputs(self) -> List[str]:
        return ["xlsx", "xls", "csv", "ods", "tsv"]

    @property
    def supported_outputs(self) -> Dict[str, List[str]]:
        return {
            "xlsx": ["csv", "pdf", "html", "ods", "tsv"],
            "xls": ["xlsx", "csv", "pdf"],
            "csv": ["xlsx", "pdf", "tsv"],
            "tsv": ["xlsx", "csv"],
            "ods": ["xlsx", "csv", "pdf"],
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

        # 1. Read input into DataFrame or openpyxl
        df = self._read_to_dataframe(input_path, ext, sheet_name=options.get("sheet_name"))

        # 2. Write to target format
        stem = input_path.stem
        out_path = output_dir / f"{stem}.{target}"

        if target == "csv":
            df.to_csv(str(out_path), index=False, encoding="utf-8")
            return [out_path]
            
        elif target == "tsv":
            df.to_csv(str(out_path), sep="\t", index=False, encoding="utf-8")
            return [out_path]

        elif target == "xlsx":
            with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Sheet1")
            return [out_path]

        elif target == "ods":
            with pd.ExcelWriter(str(out_path), engine="odf") as writer:
                df.to_excel(writer, index=False, sheet_name="Sheet1")
            return [out_path]

        elif target == "html":
            html_table = df.to_html(classes="spreadsheet-table", index=False, border=0)
            full_html = (
                "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
                f"<title>{stem}</title>"
                "<style>"
                "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; background: #f8fafc; color: #1e293b; }"
                ".table-container { overflow-x: auto; background: white; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); padding: 1rem; }"
                ".spreadsheet-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }"
                ".spreadsheet-table th, .spreadsheet-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }"
                ".spreadsheet-table th { background-color: #f1f5f9; font-weight: 600; color: #475569; }"
                ".spreadsheet-table tr:hover { background-color: #f8fafc; }"
                "</style></head><body><div class='table-container'>"
                f"<h2>{stem}</h2>{html_table}</div></body></html>"
            )
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_html)
            return [out_path]

        elif target == "pdf":
            # If LibreOffice is installed and input is XLSX/ODS, use LibreOffice for native layout
            if office_service.has_libreoffice and ext in ("xlsx", "xls", "ods"):
                try:
                    return office_service.convert_via_libreoffice(input_path, "pdf", output_dir)
                except Exception:
                    pass
            # Fallback: pure python ReportLab tabular PDF export
            return self._dataframe_to_pdf(df, stem, out_path)

        else:
            raise ValueError(f"Unsupported spreadsheet target: {target}")

    def _read_to_dataframe(self, path: Path, ext: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        if ext == "csv":
            return pd.read_csv(str(path))
        elif ext == "tsv":
            return pd.read_csv(str(path), sep="\t")
        elif ext == "xlsx":
            return pd.read_excel(str(path), sheet_name=sheet_name or 0, engine="openpyxl")
        elif ext == "xls":
            return pd.read_excel(str(path), sheet_name=sheet_name or 0, engine="xlrd")
        elif ext == "ods":
            return pd.read_excel(str(path), sheet_name=sheet_name or 0, engine="odf")
        else:
            raise ValueError(f"Unknown spreadsheet extension: {ext}")

    def _dataframe_to_pdf(self, df: pd.DataFrame, title: str, out_path: Path) -> List[Path]:
        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=landscape(letter),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading2'],
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=15
        )
        elements.append(Paragraph(title, title_style))

        # Truncate columns if excessive to fit on page
        max_cols = 12
        display_df = df.iloc[:, :max_cols].copy()
        
        # Build table matrix
        headers = [str(c) for c in display_df.columns]
        data = [headers]
        
        # Limit rows to first 100 for PDF export if huge
        max_rows = 150
        for _, row in display_df.head(max_rows).iterrows():
            data.append([str(val) if pd.notna(val) else "" for val in row])

        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#334155")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))

        elements.append(t)
        if len(df) > max_rows:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"<i>(Displaying first {max_rows} rows of {len(df)} total rows)</i>", styles['Italic']))

        doc.build(elements)
        return [out_path]

    # ================= UTILITIES =================

    def preview_data(self, file_path: Path, max_rows: int = 20) -> Dict[str, Any]:
        """Provides preview of sheets, columns, and first N rows for UI."""
        ext = file_path.suffix.lower().lstrip(".")
        sheet_names = ["Sheet1"]

        if ext in ("xlsx", "xlsm"):
            wb = openpyxl.load_workbook(str(file_path), read_only=True)
            sheet_names = wb.sheetnames
            wb.close()
        elif ext == "ods":
            # Using pandas ExcelFile to inspect sheets
            ef = pd.ExcelFile(str(file_path), engine="odf")
            sheet_names = ef.sheet_names

        # Load active sheet
        active_sheet = sheet_names[0]
        df = self._read_to_dataframe(file_path, ext, sheet_name=active_sheet)

        preview_rows = []
        for _, row in df.head(max_rows).iterrows():
            row_dict = {}
            for col in df.columns:
                val = row[col]
                row_dict[str(col)] = "" if pd.isna(val) else str(val)
            preview_rows.append(row_dict)

        return {
            "filename": file_path.name,
            "sheets": sheet_names,
            "active_sheet": active_sheet,
            "columns": [str(c) for c in df.columns],
            "rows": preview_rows,
            "total_rows": int(len(df)),
            "total_columns": int(len(df.columns))
        }

    def split_sheets(self, file_path: Path, output_dir: Path, target_ext: str = "xlsx") -> Path:
        """Splits every worksheet in an Excel workbook into its own separate file, zipped."""
        out_zip = output_dir / f"{file_path.stem}_sheets.zip"
        ext = file_path.suffix.lower().lstrip(".")
        
        if ext not in ("xlsx", "xls", "ods"):
            raise ValueError("Sheet splitting only supported for multi-sheet workbooks (.xlsx, .xls, .ods)")

        ef = pd.ExcelFile(str(file_path))
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for sheet in ef.sheet_names:
                df = ef.parse(sheet)
                safe_sheet = "".join(c for c in sheet if c.isalnum() or c in (" ", "_", "-")).strip() or "sheet"
                sheet_filename = f"{file_path.stem}_{safe_sheet}.{target_ext}"
                
                temp_file = output_dir / sheet_filename
                if target_ext == "csv":
                    df.to_csv(str(temp_file), index=False)
                else:
                    df.to_excel(str(temp_file), index=False)
                    
                zf.write(temp_file, arcname=sheet_filename)
                temp_file.unlink(missing_ok=True)

        return out_zip

    def merge_spreadsheets(self, file_paths: List[Path], output_dir: Path) -> Path:
        """Merges multiple spreadsheets into a single multi-sheet Excel workbook."""
        out_path = output_dir / "merged_workbook.xlsx"
        with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
            for p in file_paths:
                ext = p.suffix.lower().lstrip(".")
                try:
                    df = self._read_to_dataframe(p, ext)
                    sheet_name = p.stem[:30]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                except Exception as e:
                    continue
        return out_path


spreadsheet_service = SpreadsheetService()
