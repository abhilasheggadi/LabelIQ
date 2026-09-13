from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class BoundingBox(BaseModel):
    ymin: float
    xmin: float
    ymax: float
    xmax: float

class OCRTextBox(BaseModel):
    text: str
    confidence: float
    bbox: List[List[float]]  # 4-point polygon or [ymin, xmin, ymax, xmax]
    normalized_bbox: Optional[BoundingBox] = None
    field_match: Optional[str] = None
    image_index: int = 0

class QualityMetrics(BaseModel):
    glare_detected: bool = False
    glare_ratio: float = 0.0
    glare_warning: Optional[str] = None
    blur_score: float = 100.0
    blur_warning: Optional[str] = None
    card_detected: bool = False
    card_type: Optional[str] = "ID_1_STANDARD"
    card_name: Optional[str] = "ISO/IEC 7810 ID-1 Standard Card"
    card_width_pixels: Optional[float] = None
    card_height_pixels: Optional[float] = None
    mm_per_pixel: Optional[float] = None
    pdp_surface_area_cm2: Optional[float] = None
    avg_text_height_px: Optional[float] = None
    avg_text_height_mm: Optional[float] = None
    quality_passed: bool = True

class ExtractedFieldItem(BaseModel):
    field_key: str
    label: str
    category: str
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    is_present: bool = False
    is_valid: bool = False
    confidence: float = 0.0
    rule_number: str
    rule_title: str
    legal_act_section: str
    error_message: Optional[str] = None
    font_height_mm: Optional[float] = None
    min_required_font_mm: Optional[float] = None
    font_compliant: Optional[bool] = None
    bbox: Optional[List[List[float]]] = None
    image_index: Optional[int] = 0

class ViolationDetail(BaseModel):
    rule_number: str
    act_section: str = "Section 36(1) LM Act 2009"
    rule_title: str
    field_key: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    expected_format: str
    observed_value: Optional[str] = None
    statutory_citation: str
    remedy_description: str

class CorrectionUpdateRequest(BaseModel):
    inspection_uuid: str
    category: str
    corrected_fields: Dict[str, Any]
    inspector_notes: Optional[str] = None
    card_type: Optional[str] = "ID_1_STANDARD"

class ScanResponse(BaseModel):
    inspection_uuid: str
    timestamp: str
    category: str
    detected_brand: Optional[str] = None
    detected_product: Optional[str] = None
    quality: QualityMetrics
    ocr_boxes: List[OCRTextBox]
    fields: Dict[str, ExtractedFieldItem]
    verdict: str  # PASS, FAIL, WARNING
    compliance_score: float
    critical_violations_count: int
    minor_warnings_count: int
    violations: List[ViolationDetail]
    original_image_url: str
    annotated_image_url: str
    original_image_urls: List[str] = []
    annotated_image_urls: List[str] = []
    pdf_url: Optional[str] = None
    evidence_sha256: str

class InspectionSummaryResponse(BaseModel):
    id: int
    inspection_uuid: str
    timestamp: datetime
    inspector_name: str
    warehouse_name: str
    product_category: str
    product_name: Optional[str]
    verdict: str
    compliance_score: float
    critical_violations_count: int
    pdf_report_path: Optional[str]
