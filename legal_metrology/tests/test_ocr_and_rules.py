import pytest
from legal_metrology.app.services.rule_engine import rule_engine
from legal_metrology.app.services.llm_service import llm_service

import asyncio

def test_category_classification():
    food_ocr = "Nutri-Crunch Biscuits Net Wt 200g FSSAI Lic No 10019022009876 100% Veg Ingredients wheat flour"
    cat_food = asyncio.run(llm_service.classify_category(food_ocr))
    assert cat_food == "food"

    cos_ocr = "Hydrating Face Serum M.L. No. COS/123/2022 Use Before 05/2027 Batch No B109 Net Vol 50ml"
    cat_cos = asyncio.run(llm_service.classify_category(cos_ocr))
    assert cat_cos == "cosmetics"

    elec_ocr = "65W Fast Charger BIS CRS Registration R-41234567 Input 100-240V 50/60Hz Model SC-65"
    cat_elec = asyncio.run(llm_service.classify_category(elec_ocr))
    assert cat_elec == "electronics"

def test_compliant_food_evaluation():
    compliant_entities = {
        "manufacturer_name_address": {"raw_text": "Sunrise Foods Pvt Ltd, Industrial Area, Pune 411001"},
        "generic_name": {"name": "Whole Wheat Biscuits"},
        "net_quantity": {"value": 200.0, "unit": "g", "raw_text": "200 g"},
        "mfg_date": {"date_str": "08/2026", "raw_text": "08/2026"},
        "mrp": {"amount": 40.0, "taxes_included": True, "raw_text": "Rs. 40 (incl. of all taxes)"},
        "unit_sale_price": {"price": 0.20, "unit": "g", "raw_text": "Rs. 0.20 / g"},
        "consumer_care": {"phone": "1800-200-4567", "email": "care@sunrise.in", "raw_text": "care@sunrise.in"},
        "country_of_origin": {"country": "India", "raw_text": "Made in India"},
        "fssai_license": {"license_no": "10019022009876", "raw_text": "FSSAI 10019022009876"},
        "veg_nonveg_logo": {"type": "VEG", "raw_text": "100% Veg"},
        "best_before_expiry": {"value": "6 months", "raw_text": "Best before 6 months"},
        "ingredients_list": {"ingredients": "Wheat flour, sugar, oil", "raw_text": "Ingredients: Wheat flour"}
    }

    fields, violations, verdict, score = rule_engine.evaluate_compliance(compliant_entities, category="food")
    assert verdict == "PASS"
    assert score >= 90.0
    assert len([v for v in violations if v.severity == "CRITICAL"]) == 0

def test_violation_missing_mrp_taxes_and_fssai():
    non_compliant_entities = {
        "manufacturer_name_address": {"raw_text": "Apex Agro Ltd, Haridwar"},
        "generic_name": {"name": "Instant Noodles"},
        "net_quantity": {"value": 150.0, "unit": "g"},
        "mfg_date": {"date_str": "05/2026"},
        "mrp": {"amount": 35.0, "taxes_included": False, "raw_text": "Rs. 35"},  # Missing taxes clause
        # Missing USP
        # Missing FSSAI
        # Missing Veg logo
    }

    fields, violations, verdict, score = rule_engine.evaluate_compliance(non_compliant_entities, category="food")
    assert verdict == "FAIL"
    assert len(violations) >= 3
    
    violated_keys = [v.field_key for v in violations]
    assert "fssai_license" in violated_keys
    assert "veg_nonveg_logo" in violated_keys
    assert "unit_sale_price" in violated_keys

def test_rule_7_font_size_verification():
    # Net quantity 500g requires min 4.0mm font height
    # Simulated detected font height of 10 pixels with mm_per_pixel = 0.18 -> 1.8mm (Non-compliant!)
    entities = {
        "net_quantity": {"value": 500.0, "unit": "g", "height_px": 10.0, "raw_text": "Net Wt: 500 g"},
        "manufacturer_name_address": {"raw_text": "Global Foods Ltd, Delhi"},
        "generic_name": {"name": "Corn Flakes"},
        "mfg_date": {"date_str": "01/2026"},
        "mrp": {"amount": 150.0, "taxes_included": True},
        "unit_sale_price": {"price": 0.30, "unit": "g"},
        "consumer_care": {"phone": "1800-111-2222"},
        "country_of_origin": {"country": "India"},
        "fssai_license": {"license_no": "10019022009876"},
        "veg_nonveg_logo": {"type": "VEG"},
        "best_before_expiry": {"value": "01/2027"},
        "ingredients_list": {"ingredients": "Corn, Sugar"}
    }

    fields, violations, verdict, score = rule_engine.evaluate_compliance(
        entities, category="food", mm_per_pixel=0.18
    )
    # Font height = 10 * 0.18 = 1.8mm < 4.0mm required for 500g package!
    assert fields["net_quantity"].font_compliant is False
    assert fields["net_quantity"].font_height_mm == 1.8
    assert any("Rule 7" in v.rule_number for v in violations)
