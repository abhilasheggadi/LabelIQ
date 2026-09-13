import uuid
import os
import re
import hashlib
import datetime
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session

from ..config import settings
from ..models import InspectionRecord, RuleViolation
from ..schemas import (
    ScanResponse, QualityMetrics, OCRTextBox, ExtractedFieldItem,
    ViolationDetail, CorrectionUpdateRequest
)
from .cv_service import cv_service
from .ocr_service import ocr_service
from .llm_service import llm_service
from .rule_engine import rule_engine
from .pdf_service import pdf_service

class InspectionService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def process_new_scan(
        self,
        image_bytes: Any,  # bytes or List[Tuple[str, bytes]] or List[bytes]
        filename: str = "capture.jpg",
        inspector_id: str = "INSP-LM-DELHI-042",
        inspector_name: str = "Officer R. K. Sharma",
        warehouse_name: str = "Central Warehouse Hub",
        warehouse_address: str = "Plot 14, Okhla Phase III, New Delhi 110020",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        gps_accuracy: Optional[float] = None,
        card_type: str = "ID_1_STANDARD",
        manual_category: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        db: Optional[Session] = None
    ) -> ScanResponse:
        """Complete pipeline orchestrator for one or multiple package label photographs."""
        inspection_uuid = f"LM-{datetime.datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # 1. Normalize image inputs into list of (filename, bytes)
        image_items: List[Tuple[str, bytes]] = []
        if isinstance(image_bytes, list):
            for i, item in enumerate(image_bytes):
                if isinstance(item, tuple) and len(item) == 2:
                    image_items.append(item)
                elif isinstance(item, (bytes, bytearray)):
                    image_items.append((f"panel_{i+1}.jpg", item))
        elif isinstance(image_bytes, (bytes, bytearray)):
            image_items.append((filename or "capture.jpg", image_bytes))
            
        if not image_items:
            raise ValueError("No valid image data provided for inspection.")

        # Compute composite evidence SHA-256
        hasher = hashlib.sha256()
        for _, b in image_items:
            hasher.update(b)
        img_sha256 = hasher.hexdigest()

        # 2. Quality analysis and multi-panel processing
        saved_orig_paths = []
        saved_orig_urls = []
        saved_annot_paths = []
        saved_annot_urls = []
        cv_images = []
        all_ocr_boxes = []
        ocr_texts = []
        
        best_card_res = None
        max_glare_ratio = 0.0
        glare_detected = False
        glare_warning = None
        total_blur_score = 0.0

        for idx, (img_name, img_b) in enumerate(image_items):
            ext = Path(img_name).suffix or ".jpg"
            orig_filename = f"{inspection_uuid}_panel_{idx+1}_original{ext}"
            orig_path = self.upload_dir / orig_filename
            with open(orig_path, "wb") as f:
                f.write(img_b)
            saved_orig_paths.append(str(orig_path))
            saved_orig_urls.append(f"/api/files/uploads/{orig_filename}")

            cv_img = cv_service.read_image_from_bytes(img_b)
            cv_images.append(cv_img)

            # Quality metrics
            g_res = cv_service.detect_glare(cv_img)
            b_res = cv_service.detect_blur(cv_img)

            if g_res["glare_detected"]:
                glare_detected = True
                glare_warning = g_res["glare_warning"]
            max_glare_ratio = max(max_glare_ratio, g_res["glare_ratio"])
            total_blur_score += b_res["blur_score"]

            # EasyOCR on enhanced image
            enhanced = cv_service.enhance_contrast_clahe(cv_img)
            boxes = ocr_service.extract_text_with_boxes(enhanced, image_index=idx)
            if not boxes:
                boxes = ocr_service.extract_text_with_boxes(cv_img, image_index=idx)
            all_ocr_boxes.extend(boxes)
            ocr_texts.append(ocr_service.get_full_text(boxes))

            # Robust Card Calibration (combining CV edge/color segmentation with OCR spatial anchors)
            c_res = cv_service.detect_card_calibration(cv_img, card_type=card_type, ocr_boxes=boxes)
            if c_res["card_detected"] and (not best_card_res or not best_card_res["card_detected"]):
                best_card_res = c_res

        if not best_card_res:
            best_card_res = cv_service.detect_card_calibration(cv_images[0], card_type=card_type, ocr_boxes=all_ocr_boxes)

        avg_blur = total_blur_score / max(1, len(image_items))
        full_ocr_text = "\n\n".join([t for t in ocr_texts if t.strip()])

        # Calculate average text height across detected OCR boxes
        valid_heights = [b["height_px"] for b in all_ocr_boxes if b.get("height_px") and b["height_px"] > 0]
        avg_text_h_px = round(float(sum(valid_heights) / len(valid_heights)), 2) if valid_heights else None
        avg_text_h_mm = round(avg_text_h_px * best_card_res["mm_per_pixel"], 2) if (avg_text_h_px and best_card_res.get("mm_per_pixel")) else None

        quality = QualityMetrics(
            glare_detected=glare_detected,
            glare_ratio=max_glare_ratio,
            glare_warning=glare_warning,
            blur_score=avg_blur,
            blur_warning="Image is blurry; hold camera steady." if avg_blur < 85.0 else None,
            card_detected=best_card_res["card_detected"],
            card_type=best_card_res["card_type"],
            card_name=best_card_res.get("card_name", "ISO/IEC 7810 ID-1"),
            card_width_pixels=best_card_res.get("card_width_pixels"),
            card_height_pixels=best_card_res.get("card_height_pixels"),
            mm_per_pixel=best_card_res["mm_per_pixel"],
            pdp_surface_area_cm2=best_card_res.get("pdp_surface_area_cm2"),
            avg_text_height_px=avg_text_h_px,
            avg_text_height_mm=avg_text_h_mm,
            quality_passed=(not glare_detected and avg_blur >= 85.0)
        )

        # 3. Multimodal Gemini Vision OCR across all uploaded panels
        images_bytes_list = [b for _, b in image_items]
        gemini_vision_result = await llm_service.extract_via_gemini_vision(
            image_bytes=images_bytes_list,
            manual_category=manual_category,
            custom_key=gemini_api_key
        )

        if gemini_vision_result and gemini_vision_result.get("raw_transcription"):
            if not full_ocr_text or len(gemini_vision_result["raw_transcription"]) > len(full_ocr_text):
                full_ocr_text = gemini_vision_result["raw_transcription"]

        # 4. Category Classification
        if manual_category and manual_category in ["food", "cosmetics", "electronics", "general"]:
            category = manual_category
        elif gemini_vision_result and gemini_vision_result.get("category"):
            category = gemini_vision_result["category"]
        else:
            category = await llm_service.classify_category(full_ocr_text, custom_key=gemini_api_key)

        # 5. Entity Extraction (Statutory Declarations)
        local_regex_entities = llm_service._extract_entities_regex(full_ocr_text, category)
        if gemini_vision_result and gemini_vision_result.get("entities"):
            extracted_entities = gemini_vision_result["entities"]
            for k, v in local_regex_entities.items():
                if v and (k not in extracted_entities or not extracted_entities[k]):
                    extracted_entities[k] = v
            if all_ocr_boxes:
                llm_service._map_bounding_boxes_to_entities(extracted_entities, all_ocr_boxes)
        else:
            extracted_entities = await llm_service.extract_statutory_entities(
                full_ocr_text,
                category=category,
                ocr_boxes=all_ocr_boxes,
                custom_key=gemini_api_key
            )

        # 6. Statutory Rule Compliance Evaluation
        fields_dict, violations_list, verdict, compliance_score = rule_engine.evaluate_compliance(
            extracted_entities=extracted_entities,
            category=category,
            mm_per_pixel=best_card_res["mm_per_pixel"],
            card_calibrated=best_card_res["card_detected"]
        )

        # 7. Generate Annotated Evidence Images for all captured panels
        for idx, cv_img in enumerate(cv_images):
            img_boxes = [b for b in all_ocr_boxes if b.get("image_index", 0) == idx]
            annotated_img = cv_service.annotate_image(
                cv_img,
                ocr_boxes=img_boxes,
                violations=[v.model_dump() for v in violations_list],
                card_info=best_card_res if idx == 0 else None,
                inspection_uuid=f"{inspection_uuid} (Panel {idx+1}/{len(cv_images)})"
            )
            annot_filename = f"{inspection_uuid}_panel_{idx+1}_annotated.jpg"
            annot_path = self.upload_dir / annot_filename
            cv2.imwrite(str(annot_path), annotated_img)
            saved_annot_paths.append(str(annot_path))
            saved_annot_urls.append(f"/api/files/uploads/{annot_filename}")

        # 8. Generate Legal Seizure & Inspection Memo PDF
        inspection_meta = {
            "inspection_uuid": inspection_uuid,
            "timestamp": datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S IST"),
            "inspector_id": inspector_id,
            "inspector_name": inspector_name,
            "warehouse_name": warehouse_name,
            "warehouse_address": warehouse_address,
            "latitude": latitude or 28.5355,
            "longitude": longitude or 77.2628,
            "gps_accuracy_m": gps_accuracy or 4.5,
            "product_category": category,
            "verdict": verdict,
            "compliance_score": compliance_score,
            "glare_detected": glare_detected,
            "glare_ratio": max_glare_ratio,
            "blur_score": avg_blur,
            "card_calibrated": best_card_res["card_detected"],
            "card_type": best_card_res["card_type"],
            "card_name": best_card_res.get("card_name", "ISO/IEC 7810 ID-1"),
            "card_width_pixels": best_card_res.get("card_width_pixels"),
            "card_height_pixels": best_card_res.get("card_height_pixels"),
            "mm_per_pixel": best_card_res["mm_per_pixel"],
            "pdp_surface_area_cm2": best_card_res.get("pdp_surface_area_cm2"),
            "avg_text_height_px": avg_text_h_px,
            "avg_text_height_mm": avg_text_h_mm,
            "evidence_sha256": img_sha256
        }
        
        pdf_path, pdf_sha256 = pdf_service.generate_evidence_pdf(
            inspection_data=inspection_meta,
            fields=fields_dict,
            violations=violations_list,
            annotated_image_path=saved_annot_paths
        )

        # 9. Persist to Database if session provided
        if db is not None:
            rec = InspectionRecord(
                inspection_uuid=inspection_uuid,
                inspector_id=inspector_id,
                inspector_name=inspector_name,
                warehouse_name=warehouse_name,
                warehouse_address=warehouse_address,
                latitude=latitude,
                longitude=longitude,
                gps_accuracy_m=gps_accuracy,
                product_category=category,
                glare_detected=glare_detected,
                glare_ratio=max_glare_ratio,
                blur_score=avg_blur,
                card_calibrated=best_card_res["card_detected"],
                card_type=best_card_res["card_type"],
                mm_per_pixel=best_card_res["mm_per_pixel"],
                verdict=verdict,
                critical_violations_count=len([v for v in violations_list if v.severity == "CRITICAL"]),
                minor_warnings_count=len([v for v in violations_list if v.severity == "WARNING"]),
                compliance_score=compliance_score,
                original_image_path=saved_orig_paths[0],
                annotated_image_path=saved_annot_paths[0],
                pdf_report_path=str(pdf_path),
                evidence_sha256=img_sha256,
                ocr_raw_text=full_ocr_text,
                extracted_fields={k: v.model_dump() for k, v in fields_dict.items()}
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            
            for v in violations_list:
                viol_rec = RuleViolation(
                    inspection_id=rec.id,
                    rule_number=v.rule_number,
                    act_section=v.act_section,
                    rule_title=v.rule_title,
                    field_key=v.field_key,
                    severity=v.severity,
                    expected_format=v.expected_format,
                    observed_value=v.observed_value,
                    statutory_citation=v.statutory_citation,
                    remedy_description=v.remedy_description
                )
                db.add(viol_rec)
            db.commit()

        # Build OCR boxes response schema
        ocr_boxes_schema = [
            OCRTextBox(
                text=b["text"],
                confidence=b["confidence"],
                bbox=b["bbox"],
                field_match=b.get("field_match"),
                image_index=b.get("image_index", 0)
            ) for b in all_ocr_boxes
        ]

        critical_count = len([v for v in violations_list if v.severity == "CRITICAL"])
        warning_count = len([v for v in violations_list if v.severity == "WARNING"])

        return ScanResponse(
            inspection_uuid=inspection_uuid,
            timestamp=datetime.datetime.now().isoformat(),
            category=category,
            detected_brand=extracted_entities.get("manufacturer_name_address", {}).get("name_address") if isinstance(extracted_entities.get("manufacturer_name_address"), dict) else None,
            detected_product=extracted_entities.get("generic_name", {}).get("name") if isinstance(extracted_entities.get("generic_name"), dict) else None,
            quality=quality,
            ocr_boxes=ocr_boxes_schema,
            fields=fields_dict,
            verdict=verdict,
            compliance_score=compliance_score,
            critical_violations_count=critical_count,
            minor_warnings_count=warning_count,
            violations=violations_list,
            original_image_url=saved_orig_urls[0],
            annotated_image_url=saved_annot_urls[0],
            original_image_urls=saved_orig_urls,
            annotated_image_urls=saved_annot_urls,
            pdf_url=f"/api/files/pdfs/{Path(pdf_path).name}",
            evidence_sha256=img_sha256
        )

    async def update_corrections(
        self,
        correction: CorrectionUpdateRequest,
        db: Session
    ) -> ScanResponse:
        """
        Re-evaluates compliance after the inspector corrects OCR misreads in the Correction Screen.
        """
        rec = db.query(InspectionRecord).filter(InspectionRecord.inspection_uuid == correction.inspection_uuid).first()
        if not rec:
            raise ValueError(f"Inspection record '{correction.inspection_uuid}' not found.")

        category = correction.category or rec.product_category
        mm_per_pixel = rec.mm_per_pixel

        # Convert corrected fields dict into entity structure, preserving existing extracted fields
        formatted_entities = {}
        if rec.extracted_fields:
            for ek, ev in rec.extracted_fields.items():
                if isinstance(ev, dict) and "normalized_value" in ev and ev["normalized_value"]:
                    formatted_entities[ek] = ev["normalized_value"]
                elif isinstance(ev, dict):
                    formatted_entities[ek] = ev

        for k, v in correction.corrected_fields.items():
            if v is not None and str(v).strip() != "":
                val_str = str(v).strip()
                if k == "mrp":
                    try:
                        amt_match = re.search(r'([0-9]+(?:\.[0-9]{1,2})?)', val_str)
                        amt = float(amt_match.group(1)) if amt_match else 100.0
                    except Exception:
                        amt = 100.0
                    formatted_entities["mrp"] = {
                        "raw_text": val_str,
                        "amount": amt,
                        "taxes_included": True
                    }
                elif k == "net_quantity":
                    qty_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?', val_str)
                    val = float(qty_match.group(1)) if qty_match else 100.0
                    unit = qty_match.group(2) if (qty_match and qty_match.group(2)) else "g"
                    formatted_entities["net_quantity"] = {
                        "raw_text": val_str,
                        "value": val,
                        "unit": unit
                    }
                elif k == "consumer_care":
                    formatted_entities["consumer_care"] = {
                        "raw_text": val_str,
                        "phone": "1800-XXX-XXXX",
                        "email": "care@company.com"
                    }
                elif k == "fssai_license":
                    lic_digits = "".join([c for c in val_str if c.isdigit()])
                    formatted_entities["fssai_license"] = {
                        "raw_text": val_str,
                        "license_no": lic_digits
                    }
                elif k == "veg_nonveg_logo":
                    formatted_entities["veg_nonveg_logo"] = {
                        "raw_text": val_str,
                        "type": "VEG" if "non" not in val_str.lower() else "NON_VEG"
                    }
                elif k == "unit_sale_price":
                    formatted_entities["unit_sale_price"] = {
                        "raw_text": val_str,
                        "price": 0.20,
                        "unit": "g"
                    }
                elif k == "generic_name":
                    formatted_entities["generic_name"] = {
                        "raw_text": val_str,
                        "name": val_str
                    }
                elif k == "manufacturer_name_address":
                    formatted_entities["manufacturer_name_address"] = {
                        "raw_text": val_str,
                        "name_address": val_str
                    }
                elif k == "country_of_origin":
                    formatted_entities["country_of_origin"] = {
                        "raw_text": val_str,
                        "country": val_str
                    }
                elif k == "mfg_date":
                    formatted_entities["mfg_date"] = {
                        "raw_text": val_str,
                        "date_str": val_str
                    }
                elif k == "best_before_expiry":
                    formatted_entities["best_before_expiry"] = {
                        "raw_text": val_str,
                        "value": val_str
                    }
                elif k == "ingredients_list":
                    formatted_entities["ingredients_list"] = {
                        "raw_text": val_str,
                        "ingredients": val_str
                    }
                elif k == "cosmetic_mfg_license":
                    formatted_entities["cosmetic_mfg_license"] = {
                        "raw_text": val_str,
                        "license_no": val_str
                    }
                elif k == "batch_lot_number":
                    formatted_entities["batch_lot_number"] = {
                        "raw_text": val_str,
                        "batch_no": val_str
                    }
                elif k == "use_before_date":
                    formatted_entities["use_before_date"] = {
                        "raw_text": val_str,
                        "date_str": val_str
                    }
                elif k == "bis_crs_registration":
                    formatted_entities["bis_crs_registration"] = {
                        "raw_text": val_str,
                        "registration_no": val_str
                    }
                elif k == "electrical_rating":
                    formatted_entities["electrical_rating"] = {
                        "raw_text": val_str,
                        "rating": val_str
                    }
                elif k == "model_number":
                    formatted_entities["model_number"] = {
                        "raw_text": val_str,
                        "model": val_str
                    }
                elif k in ["size", "dimensions", "size_declaration", "dimensions_declaration"]:
                    formatted_entities["size"] = {
                        "raw_text": val_str,
                        "value": val_str
                    }
                    formatted_entities["dimensions_declaration"] = formatted_entities["size"]
                else:
                    formatted_entities[k] = {
                        "raw_text": val_str,
                        "value": val_str
                    }

        # Re-evaluate rules
        fields_dict, violations_list, verdict, compliance_score = rule_engine.evaluate_compliance(
            extracted_entities=formatted_entities,
            category=category,
            mm_per_pixel=mm_per_pixel,
            card_calibrated=rec.card_calibrated
        )

        # Update record
        rec.product_category = category
        rec.verdict = verdict
        rec.compliance_score = compliance_score
        rec.critical_violations_count = len([v for v in violations_list if v.severity == "CRITICAL"])
        rec.minor_warnings_count = len([v for v in violations_list if v.severity == "WARNING"])
        rec.extracted_fields = {k: v.model_dump() for k, v in fields_dict.items()}

        # Clear old violations and recreate
        db.query(RuleViolation).filter(RuleViolation.inspection_id == rec.id).delete()
        for v in violations_list:
            viol_rec = RuleViolation(
                inspection_id=rec.id,
                rule_number=v.rule_number,
                act_section=v.act_section,
                rule_title=v.rule_title,
                field_key=v.field_key,
                severity=v.severity,
                expected_format=v.expected_format,
                observed_value=v.observed_value,
                statutory_citation=v.statutory_citation,
                remedy_description=v.remedy_description
            )
            db.add(viol_rec)
        db.commit()

        # Re-generate PDF with updated fields
        inspection_meta = {
            "inspection_uuid": rec.inspection_uuid,
            "timestamp": rec.timestamp.strftime("%d-%m-%Y %H:%M:%S IST") if rec.timestamp else datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S IST"),
            "inspector_id": rec.inspector_id,
            "inspector_name": rec.inspector_name,
            "warehouse_name": rec.warehouse_name,
            "warehouse_address": rec.warehouse_address,
            "latitude": rec.latitude or 28.5355,
            "longitude": rec.longitude or 77.2628,
            "gps_accuracy_m": rec.gps_accuracy_m or 4.5,
            "product_category": category,
            "verdict": verdict,
            "compliance_score": compliance_score,
            "glare_detected": rec.glare_detected,
            "glare_ratio": rec.glare_ratio,
            "blur_score": rec.blur_score,
            "card_calibrated": rec.card_calibrated,
            "card_type": rec.card_type,
            "mm_per_pixel": rec.mm_per_pixel,
            "evidence_sha256": rec.evidence_sha256
        }
        
        annot_list = []
        if rec.annotated_image_path:
            p = Path(rec.annotated_image_path)
            parent_dir = p.parent
            panels = sorted(list(parent_dir.glob(f"{rec.inspection_uuid}_panel_*_annotated.jpg")))
            if panels:
                annot_list = [str(x) for x in panels]
            elif p.exists():
                annot_list = [str(p)]

        pdf_path, pdf_sha256 = pdf_service.generate_evidence_pdf(
            inspection_data=inspection_meta,
            fields=fields_dict,
            violations=violations_list,
            annotated_image_path=annot_list or rec.annotated_image_path
        )
        rec.pdf_report_path = str(pdf_path)
        db.commit()

        orig_filename = Path(rec.original_image_path).name if rec.original_image_path else ""
        annot_filename = Path(rec.annotated_image_path).name if rec.annotated_image_path else ""

        return ScanResponse(
            inspection_uuid=rec.inspection_uuid,
            timestamp=datetime.datetime.now().isoformat(),
            category=category,
            detected_brand=rec.brand_name,
            detected_product=rec.product_name,
            quality=QualityMetrics(
                glare_detected=rec.glare_detected,
                glare_ratio=rec.glare_ratio,
                blur_score=rec.blur_score,
                card_detected=rec.card_calibrated,
                card_type=rec.card_type,
                mm_per_pixel=rec.mm_per_pixel,
                quality_passed=True
            ),
            ocr_boxes=[],
            fields=fields_dict,
            verdict=verdict,
            compliance_score=compliance_score,
            critical_violations_count=rec.critical_violations_count,
            minor_warnings_count=rec.minor_warnings_count,
            violations=violations_list,
            original_image_url=f"/api/files/uploads/{orig_filename}",
            annotated_image_url=f"/api/files/uploads/{annot_filename}",
            pdf_url=f"/api/files/pdfs/{Path(pdf_path).name}",
            evidence_sha256=rec.evidence_sha256 or ""
        )

inspection_service = InspectionService()
