import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from ..config import settings
from ..schemas import ExtractedFieldItem, ViolationDetail

logger = logging.getLogger(__name__)

class RuleEngine:
    def __init__(self):
        self.rules_dir = Path(__file__).resolve().parent.parent / "rules"
        self.base_rules = self._load_json(self.rules_dir / "base_rules.json")
        self.category_rules = {
            "food": self._load_json(self.rules_dir / "food.json"),
            "cosmetics": self._load_json(self.rules_dir / "cosmetics.json"),
            "electronics": self._load_json(self.rules_dir / "electronics.json"),
            "general": self._load_json(self.rules_dir / "general.json")
        }
        self.font_tiers = settings.FONT_SIZE_TIERS

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_category_config(self, category: str) -> Dict[str, Any]:
        """Combines base rules and category-specific rules."""
        cat_data = self.category_rules.get(category, self.category_rules["general"])
        merged_rules = dict(self.base_rules.get("rules", {}))
        if cat_data and "additional_rules" in cat_data:
            merged_rules.update(cat_data["additional_rules"])
        return {
            "category": category,
            "statutory_act": cat_data.get("statutory_act", self.base_rules.get("statutory_act")),
            "penal_section": self.base_rules.get("penal_section", "Section 36(1) of Legal Metrology Act, 2009"),
            "rules": merged_rules
        }

    def evaluate_compliance(
        self,
        extracted_entities: Dict[str, Any],
        category: str = "general",
        mm_per_pixel: Optional[float] = None,
        card_calibrated: bool = False
    ) -> Tuple[Dict[str, ExtractedFieldItem], List[ViolationDetail], str, float]:
        """
        Evaluates extracted label declarations against Legal Metrology Rules.
        Returns: (fields_dict, violations_list, verdict, compliance_score)
        """
        # Auto-derive domestic country of origin if Indian manufacturer address is present
        if not extracted_entities.get("country_of_origin"):
            mfr = extracted_entities.get("manufacturer_name_address")
            mfr_text = ""
            if isinstance(mfr, dict):
                mfr_text = mfr.get("name_address", "") or mfr.get("raw_text", "")
            elif isinstance(mfr, str):
                mfr_text = mfr
            
            indian_locations = [
                "india", "kolkata", "delhi", "mumbai", "pune", "sirmour", "paonta sahib", "kala amb",
                "himachal", "h.p.", "maharashtra", "gujarat", "tamil nadu", "karnataka", "bengaluru",
                "chennai", "hyderabad", "uttar pradesh", "haryana", "punjab", "rajasthan", "kerala"
            ]
            if any(loc in mfr_text.lower() for loc in indian_locations) or re.search(r'\b[1-9][0-9]{5}\b', mfr_text):
                extracted_entities["country_of_origin"] = {
                    "country": "India",
                    "raw_text": "Made in India (Domestic Manufacturer Address declared under Rule 6(1)(a))",
                    "found_on_panel": (mfr.get("found_on_panel", 1) if isinstance(mfr, dict) else 1),
                    "image_index": (mfr.get("image_index", 0) if isinstance(mfr, dict) else 0)
                }

        config = self.get_category_config(category)
        rules_map = config["rules"]
        
        evaluated_fields = {}
        violations = []
        
        mandatory_count = 0
        compliant_mandatory_count = 0
        
        # Determine net weight for font size tier check
        net_qty_val = 0.0
        if "net_quantity" in extracted_entities and isinstance(extracted_entities["net_quantity"], dict):
            net_qty_val = float(extracted_entities["net_quantity"].get("value", 0.0))
            # Convert kg / l to grams / ml for tier comparison
            unit = extracted_entities["net_quantity"].get("unit", "").lower()
            if unit in ["kg", "l", "ltr", "litre"]:
                net_qty_val *= 1000.0

        min_font_required_mm = self._get_required_font_size(net_qty_val)

        for field_key, rule in rules_map.items():
            is_mandatory = rule.get("mandatory", True)
            rule_num = rule.get("rule_number", "Rule 6(1)")
            rule_title = rule.get("rule_title", field_key.title())
            act_section = rule.get("penal_section", config["penal_section"])
            severity = rule.get("severity", "CRITICAL")
            
            if is_mandatory:
                mandatory_count += 1
                
            entity_data = extracted_entities.get(field_key)
            if not entity_data and field_key == "size":
                entity_data = extracted_entities.get("dimensions_declaration") or extracted_entities.get("dimensions")
            elif not entity_data and field_key in ["dimensions_declaration", "dimensions"]:
                entity_data = extracted_entities.get("size")
            
            field_item = ExtractedFieldItem(
                field_key=field_key,
                label=rule_title,
                category=category,
                rule_number=rule_num,
                rule_title=rule_title,
                legal_act_section=act_section,
                min_required_font_mm=min_font_required_mm if (is_mandatory and field_key == "net_quantity") else None
            )

            # Check if field is present
            if not entity_data or (isinstance(entity_data, dict) and not any(entity_data.values())):
                field_item.is_present = False
                field_item.is_valid = False
                field_item.image_index = None
                if is_mandatory:
                    field_item.error_message = f"Mandatory declaration '{rule_title}' is MISSING across all photos."
                    violations.append(ViolationDetail(
                        rule_number=rule_num,
                        act_section=act_section,
                        rule_title=rule_title,
                        field_key=field_key,
                        severity=severity,
                        expected_format=rule.get("description", "Mandatory declaration must be prominently displayed."),
                        observed_value="[NOT FOUND / OMITTED across all captured photos]",
                        statutory_citation=rule.get("statutory_citation", ""),
                        remedy_description=rule.get("remedy", "Issue notice under Section 36(1).")
                    ))
                evaluated_fields[field_key] = field_item
                continue

            # Field is present
            field_item.is_present = True
            field_item.confidence = 0.95
            
            # Format raw text / normalized values
            if isinstance(entity_data, dict):
                field_item.raw_value = entity_data.get("raw_text") or str(entity_data)
                field_item.normalized_value = entity_data
                field_item.bbox = entity_data.get("bbox")
                field_item.image_index = entity_data.get("image_index", 0)
                
                # Check Font Size ONLY for Net Quantity when physical pixel scale is provided
                height_px = entity_data.get("height_px")
                if height_px and mm_per_pixel and field_key == "net_quantity":
                    font_height_mm = round(height_px * mm_per_pixel, 2)
                    field_item.font_height_mm = font_height_mm
                    if font_height_mm < min_font_required_mm:
                        field_item.font_compliant = False
                        violations.append(ViolationDetail(
                            rule_number="Rule 7(1) Schedule II",
                            act_section=act_section,
                            rule_title=f"Font Height Non-Compliance for {rule_title}",
                            field_key=field_key,
                            severity="CRITICAL",
                            expected_format=f"Minimum font height of {min_font_required_mm} mm required for net quantity {net_qty_val:.0f}g/ml.",
                            observed_value=f"[Panel {(field_item.image_index or 0) + 1}] Observed font height: {font_height_mm} mm (Deficient by {min_font_required_mm - font_height_mm:.2f} mm)",
                            statutory_citation="Rule 7 of LMPC Rules 2011: The height of any numeral and letter for net quantity shall not be less than the minimum height specified in the Schedule II table.",
                            remedy_description="Issue compounding notice for font size violation under Rule 7."
                        ))
                    else:
                        field_item.font_compliant = True
            else:
                field_item.raw_value = str(entity_data)
                field_item.normalized_value = entity_data
                field_item.image_index = 0

            # Specific validations
            is_valid, validation_err = self._validate_specific_field(field_key, entity_data, rule)
            field_item.is_valid = is_valid
            field_item.error_message = validation_err

            if not is_valid:
                violations.append(ViolationDetail(
                    rule_number=rule_num,
                    act_section=act_section,
                    rule_title=rule_title,
                    field_key=field_key,
                    severity=severity,
                    expected_format=rule.get("description", "Standard legal format required."),
                    observed_value=field_item.raw_value,
                    statutory_citation=rule.get("statutory_citation", ""),
                    remedy_description=rule.get("remedy", "Issue rectification / penalty notice.")
                ))
            else:
                if is_mandatory:
                    compliant_mandatory_count += 1

            evaluated_fields[field_key] = field_item

        # Compute Verdict
        critical_violations = [v for v in violations if v.severity == "CRITICAL"]
        minor_warnings = [v for v in violations if v.severity == "WARNING"]
        
        if critical_violations:
            verdict = "FAIL"
        elif minor_warnings:
            verdict = "WARNING"
        else:
            verdict = "PASS"
            
        compliance_score = round((compliant_mandatory_count / max(1, mandatory_count)) * 100.0, 1)

        return evaluated_fields, violations, verdict, compliance_score

    def _get_required_font_size(self, net_qty_grams: float) -> float:
        """Returns Rule 7 minimum font height in mm based on net quantity."""
        for tier in self.font_tiers:
            if net_qty_grams <= tier["max_qty"]:
                return tier["min_font_mm"]
        return 6.0

    def _validate_specific_field(self, field_key: str, entity_data: Any, rule: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Applies field-specific statutory sanity checks."""
        if field_key == "mrp":
            if isinstance(entity_data, dict):
                amount = entity_data.get("amount")
                if not amount or amount <= 0:
                    return False, "MRP amount could not be parsed or is 0."
                raw_t = (entity_data.get("raw_text") or "").lower()
                taxes_inc = entity_data.get("taxes_included", True)
                if "tax" in raw_t or "incl" in raw_t:
                    taxes_inc = True
                if rule.get("requires_taxes_clause") and not taxes_inc:
                    return False, "Mandatory phrase '(inclusive of all taxes)' is missing after MRP."
            return True, None

        if field_key == "fssai_license":
            if isinstance(entity_data, dict):
                lic_no = str(entity_data.get("license_no", "")).strip()
                if len(lic_no) != 14 or not lic_no.isdigit():
                    return False, f"FSSAI License number must be exactly 14 numeric digits (Found: '{lic_no}')."
            return True, None

        if field_key == "net_quantity":
            if isinstance(entity_data, dict):
                val = entity_data.get("value")
                unit = entity_data.get("unit")
                if not val or val <= 0:
                    return False, "Net quantity value must be greater than zero."
                std_units = rule.get("standard_units", ["g", "kg", "ml", "l", "N", "U", "pcs"])
                if unit and unit.lower() not in [u.lower() for u in std_units]:
                    return False, f"Unit '{unit}' is non-standard. Standard metric units (g, kg, ml, l, N) required under Rule 12."
            return True, None

        if field_key == "consumer_care":
            if isinstance(entity_data, dict):
                phone = entity_data.get("phone")
                email = entity_data.get("email")
                if not phone and not email:
                    return False, "Consumer care must declare at least a valid telephone number or email address."
            return True, None

        return True, None

rule_engine = RuleEngine()
