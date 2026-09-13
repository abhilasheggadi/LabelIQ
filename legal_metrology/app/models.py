import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base

class InspectionRecord(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    inspection_uuid = Column(String(64), unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Inspector & Location context (Vital for legally defensible seizure / notice)
    inspector_id = Column(String(100), default="INSP-LM-DELHI-042")
    inspector_name = Column(String(200), default="Officer R. K. Sharma")
    warehouse_name = Column(String(255), default="Central Distribution Warehouse")
    warehouse_address = Column(Text, default="Plot 14, Okhla Industrial Area Phase III, New Delhi, 110020")
    
    # Geolocation metadata
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    gps_accuracy_m = Column(Float, nullable=True)
    gps_address = Column(Text, nullable=True)
    
    # Product identification
    product_category = Column(String(50), default="general")  # food, cosmetics, electronics, general
    product_name = Column(String(255), nullable=True)
    brand_name = Column(String(255), nullable=True)
    batch_lot_number = Column(String(100), nullable=True)
    
    # CV Quality & Calibration
    glare_detected = Column(Boolean, default=False)
    glare_ratio = Column(Float, default=0.0)
    blur_score = Column(Float, default=100.0)
    card_calibrated = Column(Boolean, default=False)
    card_type = Column(String(50), nullable=True, default="ID_1_STANDARD")
    mm_per_pixel = Column(Float, nullable=True)
    
    # Verdict summary
    verdict = Column(String(20), default="PENDING")  # PASS, FAIL, WARNING
    critical_violations_count = Column(Integer, default=0)
    minor_warnings_count = Column(Integer, default=0)
    compliance_score = Column(Float, default=0.0)  # 0 to 100%
    legal_summary = Column(Text, nullable=True)
    
    # Image & File references
    original_image_path = Column(String(500), nullable=True)
    annotated_image_path = Column(String(500), nullable=True)
    pdf_report_path = Column(String(500), nullable=True)
    evidence_sha256 = Column(String(64), nullable=True)  # Cryptographic chain of custody
    
    # Full OCR raw text and JSON dump
    ocr_raw_text = Column(Text, nullable=True)
    extracted_fields = Column(JSON, default=dict)
    
    # Relationships
    violations = relationship("RuleViolation", back_populates="inspection", cascade="all, delete-orphan")

class RuleViolation(Base):
    __tablename__ = "rule_violations"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"))
    
    rule_number = Column(String(50))      # e.g. "Rule 6(1)(e)", "Rule 7(1)"
    act_section = Column(String(50), default="Section 36(1) LM Act 2009") # Legal penal section
    rule_title = Column(String(255))      # e.g. "Maximum Retail Price (MRP) Declaration"
    field_key = Column(String(100))       # e.g. "mrp", "unit_sale_price"
    severity = Column(String(20))         # "CRITICAL", "WARNING", "INFO"
    
    expected_format = Column(Text, nullable=True)
    observed_value = Column(Text, nullable=True)
    statutory_citation = Column(Text, nullable=True) # Full legal text
    remedy_description = Column(Text, nullable=True) # Guidance for seizure / compounding
    
    inspection = relationship("InspectionRecord", back_populates="violations")
