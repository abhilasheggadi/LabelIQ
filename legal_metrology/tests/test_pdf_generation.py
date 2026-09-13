import os
from pathlib import Path
from legal_metrology.app.services.pdf_service import pdf_service
from legal_metrology.app.services.rule_engine import rule_engine
from legal_metrology.app.schemas import ExtractedFieldItem, ViolationDetail

def test_evidence_pdf_generation():
    test_meta = {
        "inspection_uuid": "LM-TEST-20260830-A1B2C3D4",
        "timestamp": "30-08-2026 14:30:00 IST",
        "inspector_id": "INSP-LM-DELHI-042",
        "inspector_name": "Officer R. K. Sharma",
        "warehouse_name": "Okhla Central Logistics Depot",
        "warehouse_address": "Plot 14, Okhla Phase III, New Delhi",
        "latitude": 28.5355,
        "longitude": 77.2628,
        "gps_accuracy_m": 4.2,
        "product_category": "food",
        "verdict": "FAIL",
        "compliance_score": 65.0,
        "glare_detected": False,
        "glare_ratio": 0.02,
        "blur_score": 142.5,
        "coin_calibrated": True,
        "coin_type": "INR_1",
        "mm_per_pixel": 0.18,
        "evidence_sha256": "4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef01"
    }

    dummy_fields = {
        "mrp": ExtractedFieldItem(
            field_key="mrp",
            label="Maximum Retail Price (MRP)",
            category="food",
            raw_value="Rs. 50 (no taxes clause)",
            is_present=True,
            is_valid=False,
            rule_number="Rule 6(1)(e)",
            rule_title="Maximum Retail Price Declaration",
            legal_act_section="Section 36(1) LM Act 2009",
            error_message="Missing '(incl. of all taxes)'"
        ),
        "fssai_license": ExtractedFieldItem(
            field_key="fssai_license",
            label="FSSAI License",
            category="food",
            raw_value=None,
            is_present=False,
            is_valid=False,
            rule_number="FSSAI Reg 2.2.1(7)",
            rule_title="FSSAI License & Logo",
            legal_act_section="Section 58 FSS Act",
            error_message="Omitted"
        )
    }

    dummy_violations = [
        ViolationDetail(
            rule_number="Rule 6(1)(e)",
            act_section="Section 36(1) LM Act 2009",
            rule_title="Maximum Retail Price Declaration",
            field_key="mrp",
            severity="CRITICAL",
            expected_format="MRP ₹ XX (incl. of all taxes)",
            observed_value="Rs. 50 (no taxes clause)",
            statutory_citation="Rule 6(1)(e) of LMPC Rules 2011",
            remedy_description="Compounding notice under Section 36(1)"
        ),
        ViolationDetail(
            rule_number="FSSAI Reg 2.2.1(7)",
            act_section="Section 58 FSS Act & Rule 6(1)",
            rule_title="FSSAI License & Logo",
            field_key="fssai_license",
            severity="CRITICAL",
            expected_format="14 digit FSSAI license",
            observed_value="[NOT FOUND]",
            statutory_citation="FSSAI Labelling Regulations",
            remedy_description="Seizure memo"
        )
    ]

    pdf_path, sha256 = pdf_service.generate_evidence_pdf(
        inspection_data=test_meta,
        fields=dummy_fields,
        violations=dummy_violations,
        annotated_image_path=None
    )

    assert os.path.exists(pdf_path)
    assert Path(pdf_path).stat().st_size > 1000  # PDF generated with content
    assert len(sha256) == 64  # Valid SHA-256 hash
