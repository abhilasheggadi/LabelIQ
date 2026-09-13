import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PDF_OUTPUT_DIR = BASE_DIR / "generated_pdfs"
SAMPLES_DIR = BASE_DIR / "samples"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "LabelIQ — Legal Metrology Compliance Scanner"
    APP_VERSION: str = "2.0.0"
    API_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/metrology_scanner.db"
    
    # Gemini API for Primary Multimodal Vision & Entity Extraction
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    
    # Storage Paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    PDF_OUTPUT_DIR: Path = PDF_OUTPUT_DIR
    SAMPLES_DIR: Path = SAMPLES_DIR
    
    # CV & Quality Thresholds
    GLARE_THRESHOLD_RATIO: float = 0.08  # >8% saturated pixels = severe glare
    BLUR_LAPLACIAN_THRESHOLD: float = 85.0  # <85 variance = blurry
    
    # Standard Reference Card Dimensions (ISO/IEC 7810 ID-1 Standard)
    # 85.60 mm x 53.98 mm, Aspect Ratio: 1.586
    CARD_WIDTH_MM: float = 85.60
    CARD_HEIGHT_MM: float = 53.98
    CARD_ASPECT_RATIO: float = 1.586  # 85.60 / 53.98
    CARD_ASPECT_TOLERANCE: float = 0.22  # 1.586 ± 0.22 (robust to perspective angle)
    
    # Standard Card types
    CARD_TYPES: dict = {
        "ID_1_STANDARD": {"name": "ISO/IEC 7810 ID-1 (85.60 x 53.98 mm)", "width_mm": 85.60, "height_mm": 53.98, "ratio": 1.586},
        "GOVT_ID": {"name": "Aadhaar / PAN / Driver License / Official ID Card", "width_mm": 85.60, "height_mm": 53.98, "ratio": 1.586},
        "BUSINESS_CARD": {"name": "Standard Card (85.0 x 55.0 mm)", "width_mm": 85.00, "height_mm": 55.00, "ratio": 1.545},
        "CUSTOM_TARGET": {"name": "Custom Calibration Target (85.6 mm)", "width_mm": 85.60, "height_mm": 53.98, "ratio": 1.586}
    }
    
    # Legal Metrology Rule 7 Font Size Tiers (Weight/Volume in g/ml -> Min Font Height in mm)
    # Area of principal display panel / net weight standards
    FONT_SIZE_TIERS: list = [
        {"max_qty": 50, "min_font_mm": 1.0, "rule": "Rule 7(1) Table-1"},
        {"max_qty": 200, "min_font_mm": 2.0, "rule": "Rule 7(1) Table-1"},
        {"max_qty": 1000, "min_font_mm": 4.0, "rule": "Rule 7(1) Table-1"},
        {"max_qty": float("inf"), "min_font_mm": 6.0, "rule": "Rule 7(1) Table-1"}
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
