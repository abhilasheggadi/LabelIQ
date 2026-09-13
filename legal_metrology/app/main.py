import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, Base, get_db
from .models import InspectionRecord, RuleViolation
from .schemas import ScanResponse, CorrectionUpdateRequest, InspectionSummaryResponse
from .services.inspection_service import inspection_service
from .services.cv_service import cv_service
from .services.ocr_service import ocr_service

# Initialize DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Legal Metrology Compliance Scanner for Indian Government Field Inspectors"
)

# CORS middleware for mobile/PWA access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets & Templates
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ================= UI Page Routes =================

@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
@app.get("/join", response_class=HTMLResponse)
@app.get("/capture", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def serve_index():
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Legal Metrology Scanner</h1>"

@app.get("/correction", response_class=HTMLResponse)
async def serve_correction_page():
    page_path = TEMPLATES_DIR / "correction.html"
    if page_path.exists():
        with open(page_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Correction Screen</h1>"

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_page():
    page_path = TEMPLATES_DIR / "dashboard.html"
    if page_path.exists():
        with open(page_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Inspection Dashboard</h1>"

# ================= API Endpoints =================

@app.post("/api/scan", response_model=ScanResponse)
async def scan_label(
    files: List[UploadFile] = File(...),
    inspector_id: str = Form("INSP-LM-DELHI-042"),
    inspector_name: str = Form("Officer R. K. Sharma"),
    warehouse_name: str = Form("Central Warehouse Hub"),
    warehouse_address: str = Form("Plot 14, Okhla Phase III, New Delhi 110020"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    card_type: str = Form("ID_1_STANDARD"),
    manual_category: Optional[str] = Form(None),
    gemini_api_key: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Main endpoint: Uploads 1 or multiple product label photos (Front, Back, Side panels),
    performs CV quality checks, OCR across panels (EasyOCR / Gemini Multimodal Vision),
    statutory rule verification, generates multi-panel Evidence PDF, and returns consolidated audit report.
    """
    try:
        image_items = []
        for f in files:
            content = await f.read()
            if content:
                image_items.append((f.filename or "capture.jpg", content))
                
        if not image_items:
            raise HTTPException(status_code=400, detail="Uploaded image file(s) are empty.")
            
        result = await inspection_service.process_new_scan(
            image_bytes=image_items,
            inspector_id=inspector_id,
            inspector_name=inspector_name,
            warehouse_name=warehouse_name,
            warehouse_address=warehouse_address,
            latitude=latitude,
            longitude=longitude,
            gps_accuracy=gps_accuracy,
            card_type=card_type,
            manual_category=manual_category,
            gemini_api_key=gemini_api_key,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inspection failed: {str(e)}")

@app.post("/api/corrections", response_model=ScanResponse)
async def update_corrections(
    correction: CorrectionUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Re-evaluates compliance after the inspector corrects any OCR errors on the Correction Screen.
    """
    try:
        result = await inspection_service.update_corrections(correction, db)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correction update failed: {str(e)}")

@app.get("/api/inspections", response_model=List[InspectionSummaryResponse])
async def list_inspections(
    category: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieves list of past inspection records for warehouse audit trail."""
    query = db.query(InspectionRecord).order_by(InspectionRecord.timestamp.desc())
    if category:
        query = query.filter(InspectionRecord.product_category == category)
    if verdict:
        query = query.filter(InspectionRecord.verdict == verdict.upper())
    records = query.limit(limit).all()
    return records

@app.get("/api/inspections/{inspection_uuid}", response_model=ScanResponse)
async def get_inspection_detail(
    inspection_uuid: str,
    db: Session = Depends(get_db)
):
    """Fetches full inspection details by UUID."""
    rec = db.query(InspectionRecord).filter(InspectionRecord.inspection_uuid == inspection_uuid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Inspection not found")
        
    orig_filename = Path(rec.original_image_path).name if rec.original_image_path else ""
    annot_filename = Path(rec.annotated_image_path).name if rec.annotated_image_path else ""
    pdf_filename = Path(rec.pdf_report_path).name if rec.pdf_report_path else ""

    # Reconstruct violations
    violations = [
        {
            "rule_number": v.rule_number,
            "act_section": v.act_section,
            "rule_title": v.rule_title,
            "field_key": v.field_key,
            "severity": v.severity,
            "expected_format": v.expected_format,
            "observed_value": v.observed_value,
            "statutory_citation": v.statutory_citation,
            "remedy_description": v.remedy_description
        } for v in rec.violations
    ]

    return ScanResponse(
        inspection_uuid=rec.inspection_uuid,
        timestamp=rec.timestamp.isoformat(),
        category=rec.product_category,
        detected_brand=rec.brand_name,
        detected_product=rec.product_name,
        quality={
            "glare_detected": rec.glare_detected,
            "glare_ratio": rec.glare_ratio,
            "blur_score": rec.blur_score,
            "card_detected": rec.card_calibrated,
            "card_type": rec.card_type,
            "mm_per_pixel": rec.mm_per_pixel,
            "quality_passed": True
        },
        ocr_boxes=[],
        fields=rec.extracted_fields or {},
        verdict=rec.verdict,
        compliance_score=rec.compliance_score,
        critical_violations_count=rec.critical_violations_count,
        minor_warnings_count=rec.minor_warnings_count,
        violations=violations,
        original_image_url=f"/api/files/uploads/{orig_filename}",
        annotated_image_url=f"/api/files/uploads/{annot_filename}",
        pdf_url=f"/api/files/pdfs/{pdf_filename}",
        evidence_sha256=rec.evidence_sha256 or ""
    )

# File download endpoints
@app.get("/api/files/uploads/{filename}")
async def get_uploaded_file(filename: str):
    file_path = settings.UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/api/files/pdfs/{filename}")
async def get_pdf_file(filename: str):
    file_path = settings.PDF_OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)

@app.get("/api/samples/{filename}")
async def get_sample_file(filename: str):
    file_path = settings.SAMPLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(file_path)

@app.get("/api/samples")
async def list_sample_files():
    """Lists built-in test packages for instant 1-touch demo."""
    samples = [
        {
            "id": "food_compliant",
            "name": "Food: Nutri-Crunch Biscuits (Compliant)",
            "filename": "sample_food_compliant.jpg",
            "category": "food",
            "expected_verdict": "PASS"
        },
        {
            "id": "food_violation",
            "name": "Food: Masala Noodles (Violations: No Veg Logo, No Taxes Clause, No USP)",
            "filename": "sample_food_violation.jpg",
            "category": "food",
            "expected_verdict": "FAIL"
        },
        {
            "id": "cosmetics_violation",
            "name": "Cosmetics: Face Serum (Violations: Missing Mfg License & Batch No)",
            "filename": "sample_cosmetics_violation.jpg",
            "category": "cosmetics",
            "expected_verdict": "FAIL"
        },
        {
            "id": "electronics_compliant",
            "name": "Electronics: 65W GaN Charger + Calibrated Coin (Compliant BIS)",
            "filename": "sample_electronics_compliant.jpg",
            "category": "electronics",
            "expected_verdict": "PASS"
        }
    ]
    return samples

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "gpu_available": ocr_service.gpu_available,
        "easyocr_ready": ocr_service.reader is not None
    }
