from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ConversionOption(BaseModel):
    id: str
    name: str
    category: str
    input_format: str
    output_format: str
    description: str
    requires_libreoffice: bool = False
    requires_tesseract: bool = False
    requires_poppler: bool = False
    is_available: bool = True
    limitations: Optional[str] = None


class CategoryConversions(BaseModel):
    category_id: str
    name: str
    description: str
    formats: List[str]
    conversions: List[ConversionOption]
    utilities: List[Dict[str, Any]] = Field(default_factory=list)


class ConversionRegistryResponse(BaseModel):
    categories: Dict[str, CategoryConversions]
    supported_inputs: List[str]
    max_file_size_mb: int
    system_capabilities: Dict[str, bool]


class ConvertResponse(BaseModel):
    job_id: str
    status: str
    target_format: str
    output_filename: Optional[str] = None
    output_files: List[str] = Field(default_factory=list)
    download_url: Optional[str] = None
    error: Optional[str] = None


class SpreadsheetPreviewResponse(BaseModel):
    filename: str
    sheets: List[str]
    active_sheet: str
    columns: List[str]
    rows: List[List[Any]]
    total_rows: int
    total_columns: int
