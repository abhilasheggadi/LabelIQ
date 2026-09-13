import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from legal_metrology.app.main import app
from legal_metrology.app.config import settings

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Legal Metrology" in data["app"]

def test_samples_endpoint():
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) >= 4
    categories = [s["category"] for s in samples]
    assert "food" in categories
    assert "cosmetics" in categories
    assert "electronics" in categories

def test_scan_sample_image():
    sample_path = settings.SAMPLES_DIR / "sample_food_compliant.jpg"
    assert sample_path.exists()

    with open(sample_path, "rb") as f:
        response = client.post(
            "/api/scan",
            files=[("files", ("sample_food_compliant.jpg", f, "image/jpeg"))],
            data={
                "inspector_id": "INSP-TEST-001",
                "inspector_name": "Test Inspector",
                "warehouse_name": "Test Warehouse Hub",
                "warehouse_address": "Test Address, Delhi",
                "latitude": 28.5355,
                "longitude": 77.2628,
                "card_type": "ID_1_STANDARD",
                "manual_category": "food"
            }
        )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["inspection_uuid"].startswith("LM-")
    assert res_data["category"] == "food"
    assert "quality" in res_data
    assert "fields" in res_data
    assert "verdict" in res_data
    assert "pdf_url" in res_data
    assert len(res_data["evidence_sha256"]) == 64
    assert len(res_data["original_image_urls"]) >= 1

def test_scan_multi_panel_images():
    p1 = settings.SAMPLES_DIR / "sample_food_compliant.jpg"
    p2 = settings.SAMPLES_DIR / "sample_food_violation.jpg"
    assert p1.exists() and p2.exists()

    with open(p1, "rb") as f1, open(p2, "rb") as f2:
        response = client.post(
            "/api/scan",
            files=[
                ("files", ("front_panel.jpg", f1, "image/jpeg")),
                ("files", ("back_panel.jpg", f2, "image/jpeg"))
            ],
            data={
                "inspector_id": "INSP-TEST-002",
                "manual_category": "food"
            }
        )

    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data["original_image_urls"]) == 2
    assert len(res_data["annotated_image_urls"]) == 2

def test_correction_re_evaluation():
    # 1. First scan food violation sample
    sample_path = settings.SAMPLES_DIR / "sample_food_violation.jpg"
    with open(sample_path, "rb") as f:
        scan_res = client.post(
            "/api/scan",
            files=[("files", ("sample_food_violation.jpg", f, "image/jpeg"))],
            data={"manual_category": "food"}
        )
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    uuid = scan_data["inspection_uuid"]

    # 2. Now submit corrections fixing the violations
    corr_payload = {
        "inspection_uuid": uuid,
        "category": "food",
        "corrected_fields": {
            "generic_name": "Instant Masala Noodles",
            "mrp": "Rs. 35.00 (incl. of all taxes)",
            "fssai_license": "10019022009876",
            "veg_nonveg_logo": "100% Veg",
            "unit_sale_price": "Rs. 0.23 / g",
            "net_quantity": "150 g",
            "mfg_date": "05/2026",
            "best_before_expiry": "12/2026",
            "manufacturer_name_address": "Apex Agro Ltd., Haridwar",
            "country_of_origin": "India",
            "consumer_care": "+91-9876543210",
            "ingredients_list": "Wheat flour, seasoning spices, edible veg oil"
        }
    }

    corr_res = client.post("/api/corrections", json=corr_payload)
    assert corr_res.status_code == 200
    updated_data = corr_res.json()
    assert updated_data["verdict"] == "PASS"
    assert updated_data["compliance_score"] >= 80.0
