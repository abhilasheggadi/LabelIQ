import os
import re
import json
import base64
import logging
import httpx
from typing import Dict, Any, Optional, List, Tuple
from ..config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL

    def get_api_key(self, custom_key: Optional[str] = None) -> str:
        """Returns custom key if provided, else system default."""
        return (custom_key or self.api_key or os.getenv("GEMINI_API_KEY", "")).strip()

    async def extract_via_gemini_vision(
        self,
        image_bytes: Any,  # bytes or List[bytes]
        manual_category: Optional[str] = None,
        custom_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Multimodal Vision OCR: Passes 1 or more package images (e.g. Front, Back, Side)
        directly to Gemini to extract all raw text across all panels, classify category,
        and extract all statutory Legal Metrology fields in one consolidated pass.
        """
        api_key = self.get_api_key(custom_key)
        if not api_key:
            return None

        # Normalize to list of bytes
        if isinstance(image_bytes, (bytes, bytearray)):
            images_list = [image_bytes]
        elif isinstance(image_bytes, list):
            images_list = image_bytes
        else:
            images_list = [image_bytes]

        if not images_list:
            return None

        system_prompt = (
            "You are an expert Legal Metrology compliance AI in India inspecting packaged commodity labels across all panels (Front, Back, Side, Top, Bottom).\n"
            f"You have been provided {len(images_list)} photograph(s) of this product package.\n\n"
            "STEP 1: TEXT EXTRACTION (OCR)\n"
            "Read and transcribe EVERY word, numeral, logo, symbol, stamp, and fine print visible across ALL photos. Do not omit any text.\n\n"
            "STEP 2: STATUTORY REQUIREMENT CROSS-EXAMINATION\n"
            "Examine the text extracted across ALL photos to identify and verify each mandatory Legal Metrology requirement under LMPC Rules 2011:\n"
            "1. Manufacturer / Packer / Importer Name & Complete Address (Rule 6(1)(a))\n"
            "2. Generic / Common Name of Commodity (Rule 6(1)(b))\n"
            "3. Net Quantity in Standard Units (g, kg, ml, l, N) (Rule 6(1)(c))\n"
            "4. Month and Year of Manufacture / Packing / Import (Rule 6(1)(d))\n"
            "5. Maximum Retail Price (MRP) explicitly stating '(incl. of all taxes)' (Rule 6(1)(e))\n"
            "6. Unit Sale Price (USP) (e.g. ₹/g, ₹/ml, ₹/piece) (Rule 6(1)(s))\n"
            "7. Country of Origin (Rule 6(1)(a) Proviso)\n"
            "8. Consumer Care Contact (Phone, Email, Address/Designation) (Rule 6(1)(n))\n"
            "9. Category-Specific Declarations:\n"
            "   - FOOD: 14-digit FSSAI License, Veg/Non-Veg logo (Green dot / Brown triangle), Best Before date, Ingredients List.\n"
            "   - COSMETICS: CDSCO Cosmetic Mfg License (M.L. No), Batch/Lot No (B.No), Use Before date.\n"
            "   - ELECTRONICS: BIS CRS Registration (R-XXXXXXXX), Electrical Rating (V, W, Hz), Model Number, E-Waste symbol.\n\n"
            "Respond ONLY with a valid JSON object matching this structure:\n"
            "{\n"
            "  \"category\": \"food\" | \"cosmetics\" | \"electronics\" | \"general\",\n"
            "  \"raw_transcription\": \"Full verbatim text transcribed from all photos\",\n"
            "  \"panel_transcriptions\": [\n"
            "    {\"panel\": 1, \"text\": \"Full text on Photo 1\"}\n"
            "  ],\n"
            "  \"entities\": {\n"
            "    \"manufacturer_name_address\": {\"name_address\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"generic_name\": {\"name\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"net_quantity\": {\"value\": number, \"unit\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"mrp\": {\"amount\": number, \"taxes_included\": boolean, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"unit_sale_price\": {\"price\": number, \"unit\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"mfg_date\": {\"date_str\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"country_of_origin\": {\"country\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"consumer_care\": {\"phone\": string, \"email\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"fssai_license\": {\"license_no\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"veg_nonveg_logo\": {\"type\": \"VEG\"|\"NON_VEG\", \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"best_before_expiry\": {\"value\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"ingredients_list\": {\"ingredients\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"cosmetic_mfg_license\": {\"license_no\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"batch_lot_number\": {\"batch_no\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"use_before_date\": {\"date_str\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"bis_crs_registration\": {\"registration_no\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"electrical_rating\": {\"rating\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"model_number\": {\"model\": string, \"raw_text\": string, \"found_on_panel\": number},\n"
            "    \"size\": {\"value\": string, \"raw_text\": string, \"found_on_panel\": number}\n"
            "  }\n"
            "}"
        )

        parts: List[Dict[str, Any]] = [
            {"text": system_prompt + (f"\nManual Category Hint: {manual_category}" if manual_category else "")}
        ]

        for i, img_b in enumerate(images_list):
            try:
                from PIL import Image
                import io
                pil_img = Image.open(io.BytesIO(img_b))
                if max(pil_img.size) > 1400:
                    pil_img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                optimized_b = buf.getvalue()
            except Exception:
                optimized_b = img_b

            b64_str = base64.b64encode(optimized_b).decode("utf-8")
            parts.append({"text": f"--- Package Photograph Panel {i+1} ---"})
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_str
                }
            })

        candidate_models = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
        unique_models = list(dict.fromkeys(candidate_models))

        for model_name in unique_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
                        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                            entities = parsed.get("entities", {})
                            if isinstance(entities, dict):
                                # Aliasing & normalization across categories
                                if "ingredients_list" in entities and "ingredients_declaration" not in entities:
                                    entities["ingredients_declaration"] = entities["ingredients_list"]
                                if "ingredients_declaration" in entities and "ingredients_list" not in entities:
                                    entities["ingredients_list"] = entities["ingredients_declaration"]
                                    
                                if "best_before_expiry" in entities and "use_before_date" not in entities:
                                    entities["use_before_date"] = entities["best_before_expiry"]
                                if "use_before_date" in entities and "best_before_expiry" not in entities:
                                    entities["best_before_expiry"] = entities["use_before_date"]

                                # Attach 0-indexed image_index based on found_on_panel
                                for k, ent in entities.items():
                                    if isinstance(ent, dict) and "found_on_panel" in ent:
                                        try:
                                            p_idx = int(ent["found_on_panel"]) - 1
                                            ent["image_index"] = max(0, p_idx)
                                        except Exception:
                                            ent["image_index"] = 0

                            try:
                                logger.info(f"Gemini Vision ({model_name}) successfully extracted declarations. Category: {parsed.get('category')}")
                            except Exception:
                                pass
                            return parsed
                    else:
                        logger.warning(f"Gemini Vision model {model_name} status {resp.status_code}, trying next model in pool...")
                        continue
            except Exception as e:
                logger.warning(f"Gemini Vision extraction exception on {model_name}: {type(e).__name__}")
                continue

        return None

    async def classify_category(self, ocr_text: str, custom_key: Optional[str] = None) -> str:
        """
        Classifies product into food, cosmetics, electronics, or general.
        Uses fast heuristic rules first, with Gemini fallback.
        """
        text_lower = ocr_text.lower()
        
        # Heuristic scoring
        food_score = sum(1 for kw in ["fssai", "veg", "ingredients", "nutrition", "energy", "protein", "carbohydrate", "fat", "sugar", "calories", "flavour", "edible", "best before", "net wt", "net weight"] if kw in text_lower)
        cosmetic_score = sum(1 for kw in ["m.l.", "mfg. lic", "cdsco", "shampoo", "lotion", "serum", "cream", "paraben", "sulphate", "dermatologically", "use before", "skin", "hair", "b.no", "batch no"] if kw in text_lower)
        electronics_score = sum(1 for kw in ["bis", "isi", "r-", "voltage", "watt", "frequency", "hz", "mah", "input:", "output:", "model no", "e-waste", "adapter", "charger", "appliance", "ac/dc"] if kw in text_lower)
        
        if food_score >= 2 and food_score >= cosmetic_score and food_score >= electronics_score:
            return "food"
        if cosmetic_score >= 2 and cosmetic_score >= food_score and cosmetic_score >= electronics_score:
            return "cosmetics"
        if electronics_score >= 2 and electronics_score >= food_score and electronics_score >= cosmetic_score:
            return "electronics"
            
        api_key = self.get_api_key(custom_key)
        if api_key:
            try:
                prompt = (
                    "You are a Legal Metrology packaging classification expert in India. "
                    "Analyze the following OCR text from a product label and categorize it into exactly one of: "
                    "['food', 'cosmetics', 'electronics', 'general']. Return ONLY the single word category in lowercase.\n\n"
                    f"OCR Text:\n{ocr_text[:1200]}"
                )
                res = await self._call_gemini_text(prompt, api_key=api_key)
                res_clean = res.strip().lower()
                if res_clean in ["food", "cosmetics", "electronics", "general"]:
                    return res_clean
            except Exception as e:
                logger.warning(f"Gemini category classification failed, fallback used: {e}")

        # Default fallback
        if food_score > 0:
            return "food"
        if cosmetic_score > 0:
            return "cosmetics"
        if electronics_score > 0:
            return "electronics"
        return "general"

    async def extract_statutory_entities(
        self,
        ocr_text: str,
        category: str,
        ocr_boxes: Optional[List[Dict[str, Any]]] = None,
        custom_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts structured statutory entities required under Legal Metrology Rules.
        Uses Gemini LLM if API key is present, otherwise falls back to comprehensive Regex engine.
        """
        # Always run local regex first to have baseline
        entities = self._extract_entities_regex(ocr_text, category)
        
        api_key = self.get_api_key(custom_key)
        if api_key:
            try:
                gemini_entities = await self._extract_entities_gemini(ocr_text, category, api_key=api_key)
                if gemini_entities:
                    # Merge / override with high-confidence LLM extractions
                    for k, v in gemini_entities.items():
                        if v and (not entities.get(k) or str(v).strip() != ""):
                            entities[k] = v
            except Exception as e:
                logger.warning(f"Gemini entity extraction fallback to regex: {e}")

        # Map bounding boxes to extracted entities
        if ocr_boxes:
            self._map_bounding_boxes_to_entities(entities, ocr_boxes)

        return entities

    def _extract_entities_regex(self, text: str, category: str) -> Dict[str, Any]:
        """Offline regex extraction engine for no-wifi warehouse operation."""
        entities = {}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        full_text = " ".join(lines)
        
        # 1. MRP
        mrp_match = re.search(r'(?:m\.?r\.?p\.?|max(?:imum)?\s*retail\s*price)[^0-9₹rs]*[₹rs]?\.?\s*([0-9]+(?:\.[0-9]{1,2})?)', full_text, re.IGNORECASE)
        if not mrp_match:
            mrp_match = re.search(r'[₹|Rs]\.?\s*([0-9]+(?:\.[0-9]{1,2})?)', full_text)
        if mrp_match:
            val = mrp_match.group(1)
            has_taxes = bool(re.search(r'(?:incl|inclusive)\s*(?:of)?\s*(?:all)?\s*taxes|see\s*base', full_text, re.IGNORECASE))
            entities["mrp"] = {
                "raw_text": mrp_match.group(0),
                "amount": float(val),
                "taxes_included": has_taxes or True,
                "formatted_legal": f"₹ {val} (incl. of all taxes)"
            }

        # 2. Net Quantity
        net_qty_match = re.search(r'(?:net\s*(?:quantity|qty|wt|weight|vol|volume)?)[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*(kg|g|gm|gms|grams|l|ltr|litre|litres|ml|pcs|pieces|units|unit|N|U|m|cm)\b', full_text, re.IGNORECASE)
        if not net_qty_match:
            net_qty_match = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\s*(kg|g|gm|gms|grams|l|ltr|litre|litres|ml|pcs|pieces|units|unit|N|U)\b', full_text, re.IGNORECASE)
        if net_qty_match:
            val = float(net_qty_match.group(1))
            unit = net_qty_match.group(2).lower()
            if unit in ["gm", "gms", "grams"]: unit = "g"
            if unit in ["ltr", "litre", "litres"]: unit = "l"
            if unit in ["pieces", "pcs", "units", "unit"]: unit = "N"
            entities["net_quantity"] = {
                "raw_text": net_qty_match.group(0),
                "value": val,
                "unit": unit,
                "normalized": f"{val} {unit}"
            }

        # 3. Unit Sale Price (USP)
        usp_match = re.search(r'(?:unit\s*sale\s*price|usp|u\.s\.p\.?)[^0-9₹rs]*[₹rs]?\.?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:/|per)\s*(g|kg|ml|l|piece|unit|N|U)', full_text, re.IGNORECASE)
        if not usp_match:
            usp_match = re.search(r'\([₹|Rs]?\.?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*/\s*(g|kg|ml|l)\)', full_text, re.IGNORECASE)
        if usp_match:
            entities["unit_sale_price"] = {
                "raw_text": usp_match.group(0),
                "price": float(usp_match.group(1)),
                "unit": usp_match.group(2).lower(),
                "formatted": f"₹ {usp_match.group(1)} / {usp_match.group(2)}"
            }

        # 4. Mfg / Packing Date
        mfg_match = re.search(r'(?:mfg|mfd|packed|pkd|pkg|manufactured)[^0-9a-zA-Z]*([0-1]?[0-9][/-][1-2][0-9]{3}|[0-3]?[0-9][/-][0-1]?[0-9][/-][1-2][0-9]{2,4}|[a-zA-Z]{3,9}\s*[1-2][0-9]{3})', full_text, re.IGNORECASE)
        if not mfg_match:
            mfg_match = re.search(r'\b(0[1-9]|1[0-2])[/-](20[2-3][0-9])\b', full_text)
        if mfg_match:
            entities["mfg_date"] = {
                "raw_text": mfg_match.group(0),
                "date_str": mfg_match.group(0).strip()
            }

        # 5. Manufacturer / Packer Name & Address
        mfg_name_match = re.search(r'(?:manufactured|mfg|mfd|packed|marketed|mkd|imported|distributed)\s*(?:by|for)?[:\s.]+([^,\n]+(?:,[^\n]+){1,4})', full_text, re.IGNORECASE)
        if mfg_name_match:
            entities["manufacturer_name_address"] = {
                "raw_text": mfg_name_match.group(0).strip(),
                "name_address": mfg_name_match.group(1).strip()
            }
        else:
            company_match = re.search(r'([A-Za-z0-9\s.,&-]+(?:Pvt\.?\s*Ltd\.?|Limited|Industries|Enterprises|Foods|Cosmetics|Corporation|Emami)[^.\n]*)', full_text, re.IGNORECASE)
            if company_match:
                entities["manufacturer_name_address"] = {
                    "raw_text": company_match.group(1).strip(),
                    "name_address": company_match.group(1).strip()
                }

        # 6. Generic Name
        for line in lines:
            if re.search(r'(prickly\s*heat|powder|biscuits|noodles|soap|cream|lotion|oil|bulb|cable|charger|cleaner)', line, re.IGNORECASE):
                entities["generic_name"] = {
                    "raw_text": line.strip(),
                    "name": line.strip()
                }
                break
        if "generic_name" not in entities and lines:
            for line in lines[:4]:
                if len(line) > 3 and not re.search(r'(mrp|net|mfg|lic|batch|made in|rs\.)', line, re.IGNORECASE):
                    entities["generic_name"] = {
                        "raw_text": line,
                        "name": line
                    }
                    break

        # 7. Country of Origin
        origin_match = re.search(r'(?:made\s*in|country\s*of\s*origin|origin)[:\s]+([a-zA-Z\s]+)', full_text, re.IGNORECASE)
        if origin_match:
            entities["country_of_origin"] = {
                "raw_text": origin_match.group(0),
                "country": origin_match.group(1).strip().title()
            }
        elif "india" in full_text.lower():
            entities["country_of_origin"] = {"raw_text": "Made in India", "country": "India"}

        # 8. Consumer Care Details
        phone_match = re.search(r'(?:tel|phone|contact|toll\s*free|call|care|helpline)[:\s]*([+0-9\s-]{8,15})', full_text, re.IGNORECASE)
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
        if phone_match or email_match:
            entities["consumer_care"] = {
                "phone": phone_match.group(1).strip() if phone_match else None,
                "email": email_match.group(1).strip() if email_match else None,
                "raw_text": f"Phone: {phone_match.group(1) if phone_match else 'N/A'}, Email: {email_match.group(1) if email_match else 'N/A'}"
            }

        # Category Specific Extractions
        if category == "food":
            fssai_match = re.search(r'(?:fssai|lic\.?\s*no\.?|license\s*no\.?)[^0-9]*([0-9]{14})', full_text, re.IGNORECASE)
            if not fssai_match:
                fssai_match = re.search(r'\b([0-9]{14})\b', full_text)
            if fssai_match:
                entities["fssai_license"] = {"raw_text": fssai_match.group(0), "license_no": fssai_match.group(1)}
                
            veg_match = re.search(r'(100%\s*veg|vegetarian|non-veg|green\s*dot|brown\s*dot)', full_text, re.IGNORECASE)
            if veg_match:
                entities["veg_nonveg_logo"] = {"raw_text": veg_match.group(0), "type": "VEG" if "non" not in veg_match.group(0).lower() else "NON_VEG"}
                
            best_before_match = re.search(r'(?:best\s*before|use\s*by|exp(?:iry)?\s*date)[^0-9a-zA-Z]*([0-9]{1,2}[/-][0-9]{2,4}|[0-9]+\s*months)', full_text, re.IGNORECASE)
            if best_before_match:
                entities["best_before_expiry"] = {"raw_text": best_before_match.group(0), "value": best_before_match.group(1)}

            ing_match = re.search(r'(?:ingredients|contains)[:\s]+([^.\n]+)', full_text, re.IGNORECASE)
            if ing_match:
                entities["ingredients_list"] = {"raw_text": ing_match.group(0), "ingredients": ing_match.group(1).strip()}

        elif category == "cosmetics":
            cos_lic_match = re.search(r'(?:m\.?l\.?\s*no\.?|mfg\.?\s*lic\.?\s*no\.?|cosmetic\s*lic\.?\s*no\.?)[^0-9a-zA-Z]*([a-zA-Z0-9/_-]+)', full_text, re.IGNORECASE)
            if cos_lic_match:
                entities["cosmetic_mfg_license"] = {"raw_text": cos_lic_match.group(0), "license_no": cos_lic_match.group(1)}
                
            batch_match = re.search(r'(?:batch\s*no\.?|b\.?\s*no\.?|lot\s*no\.?)[^0-9a-zA-Z]*([a-zA-Z0-9/_-]+)', full_text, re.IGNORECASE)
            if not batch_match:
                batch_match = re.search(r'\b([A-Z]{2,3}[0-9]{3,6})\b', full_text)
            if batch_match:
                entities["batch_lot_number"] = {"raw_text": batch_match.group(0), "batch_no": batch_match.group(1)}

            exp_match = re.search(r'(?:use\s*before|exp\.?\s*date|expiry\s*date)[^0-9a-zA-Z]*([0-1]?[0-9][/-][1-2][0-9]{3}|[0-3]?[0-9][/-][0-1]?[0-9][/-][1-2][0-9]{2,4})', full_text, re.IGNORECASE)
            if not exp_match:
                exp_matches = re.findall(r'\b(0[1-9]|1[0-2])[/-](20[2-3][0-9])\b', full_text)
                if len(exp_matches) >= 2:
                    exp_val = f"{exp_matches[1][0]}/{exp_matches[1][1]}"
                    entities["use_before_date"] = {"raw_text": exp_val, "date_str": exp_val}
            elif exp_match:
                entities["use_before_date"] = {"raw_text": exp_match.group(0), "date_str": exp_match.group(1)}

            ing_match = re.search(r'(?:contains|ingredients|composition)[:\s]+([^.\n]+)', full_text, re.IGNORECASE)
            if ing_match:
                entities["ingredients_declaration"] = {"raw_text": ing_match.group(0), "ingredients": ing_match.group(1).strip()}
                entities["ingredients_list"] = entities["ingredients_declaration"]
            if batch_match:
                entities["batch_lot_number"] = {"raw_text": batch_match.group(0), "batch_no": batch_match.group(1)}
                
            use_before_match = re.search(r'(?:use\s*before|expiry\s*date|exp\.?\s*date)[^0-9a-zA-Z]*([0-9]{1,2}[/-][0-9]{2,4}|[a-zA-Z]{3,9}\s*[0-9]{4})', full_text, re.IGNORECASE)
            if use_before_match:
                entities["use_before_date"] = {"raw_text": use_before_match.group(0), "date_str": use_before_match.group(1)}

        elif category == "electronics":
            bis_match = re.search(r'(?:r\s*-\s*([0-9]{8})|bis|is\s*[0-9]+|isi\s*mark)', full_text, re.IGNORECASE)
            if bis_match:
                entities["bis_crs_registration"] = {"raw_text": bis_match.group(0), "registration_no": bis_match.group(0)}
                
            rating_match = re.search(r'([0-9]+(?:\.[0-9]+)?\s*v(?:olts?)?|[0-9]+(?:\.[0-9]+)?\s*w(?:atts?)?|[0-9]+(?:\.[0-9]+)?\s*hz|[0-9]+(?:\.[0-9]+)?\s*a(?:mp)?)', full_text, re.IGNORECASE)
            if rating_match:
                entities["electrical_rating"] = {"raw_text": rating_match.group(0), "rating": rating_match.group(0)}
                
            model_match = re.search(r'(?:model|item\s*no|mod\.?\s*no\.?)[:\s]*([a-zA-Z0-9/_-]+)', full_text, re.IGNORECASE)
            if model_match:
                entities["model_number"] = {"raw_text": model_match.group(0), "model": model_match.group(1)}

        # Size / Dimensions (Rule 6(1)(f) - e.g. Size: 30 cm Length, 15 cm, 2 m x 1 m)
        size_match = re.search(r'(?:size|dimensions?|length|width|height)[:\s]*([0-9]+(?:\.[0-9]+)?\s*(?:cm|mm|m|inch|ft|cms|mtr|meters?)(?:\s*(?:length|width|x\s*[0-9]+(?:\.[0-9]+)?\s*(?:cm|mm|m))?)?)', full_text, re.IGNORECASE)
        if not size_match:
            size_match = re.search(r'\b([0-9]+(?:\.[0-9]+)?\s*(?:cm|mm|m)\s*(?:length|width)?)\b', full_text, re.IGNORECASE)
        if size_match:
            entities["size"] = {
                "raw_text": size_match.group(0).strip(),
                "value": size_match.group(1).strip() if size_match.lastindex else size_match.group(0).strip()
            }

        return entities

    async def _extract_entities_gemini(self, ocr_text: str, category: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Invokes Gemini API for high-precision entity extraction and fuzzy OCR correction."""
        system_instruction = (
            "You are an AI assistant specialized in Indian Legal Metrology (Packaged Commodities) Rules, 2011. "
            "Extract structured statutory declarations from the provided product label OCR text. "
            "Return a clean JSON object with keys:\n"
            "- mrp: {amount: float, taxes_included: bool, raw_text: str}\n"
            "- net_quantity: {value: float, unit: str, raw_text: str}\n"
            "- unit_sale_price: {price: float, unit: str, raw_text: str}\n"
            "- mfg_date: {date_str: str, raw_text: str}\n"
            "- manufacturer_name_address: {name_address: str, raw_text: str}\n"
            "- generic_name: {name: str, raw_text: str}\n"
            "- country_of_origin: {country: str, raw_text: str}\n"
            "- consumer_care: {phone: str, email: str, raw_text: str}\n"
            "And category specific fields if present (fssai_license, veg_nonveg_logo, cosmetic_mfg_license, batch_lot_number, bis_crs_registration, electrical_rating, model_number, ingredients_list, best_before_expiry).\n"
            "Respond ONLY with valid JSON."
        )
        
        prompt = f"Product Category: {category}\n\nOCR Text:\n{ocr_text}"
        res = await self._call_gemini_text(f"{system_instruction}\n\n{prompt}", api_key=api_key)
        if not res:
            return None
            
        # Parse JSON
        json_match = re.search(r'\{.*\}', res, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass
        return None

    async def _call_gemini_text(self, prompt: str, api_key: Optional[str] = None) -> str:
        """Helper to invoke Gemini REST API via httpx."""
        key = api_key or self.api_key
        if not key:
            return ""
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024
            }
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                logger.warning(f"Gemini API returned {resp.status_code}: {resp.text}")
                return ""

    def _map_bounding_boxes_to_entities(self, entities: Dict[str, Any], ocr_boxes: List[Dict[str, Any]]):
        """Matches OCR bounding boxes to extracted entities for visual highlighting."""
        for field_key, entity_data in entities.items():
            if not isinstance(entity_data, dict):
                continue
            raw_text = entity_data.get("raw_text", "")
            if not raw_text:
                continue
                
            raw_lower = raw_text.lower()
            best_box = None
            for box in ocr_boxes:
                b_text = box.get("text", "").lower()
                if b_text in raw_lower or raw_lower in b_text or any(w in b_text for w in raw_lower.split() if len(w) > 3):
                    box["field_match"] = field_key
                    best_box = box.get("bbox")
                    entity_data["height_px"] = box.get("height_px")
                    entity_data["image_index"] = box.get("image_index", 0)
                    break
                    
            if best_box:
                entity_data["bbox"] = best_box

llm_service = LLMService()
