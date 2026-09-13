import cv2
import numpy as np
from PIL import Image, ImageOps
import io
import math
from typing import Tuple, Dict, Any, Optional, List
from ..config import settings

class CVService:
    def __init__(self):
        self.glare_threshold_ratio = settings.GLARE_THRESHOLD_RATIO
        self.blur_laplacian_threshold = settings.BLUR_LAPLACIAN_THRESHOLD
        self.card_width_mm = settings.CARD_WIDTH_MM
        self.card_height_mm = settings.CARD_HEIGHT_MM
        self.card_aspect_ratio = settings.CARD_ASPECT_RATIO
        self.card_aspect_tolerance = settings.CARD_ASPECT_TOLERANCE
        self.card_types = settings.CARD_TYPES

    def read_image_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Loads an image from raw bytes, handling EXIF orientation properly."""
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = ImageOps.exif_transpose(pil_img)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return cv_img

    def detect_glare(self, image_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Detects bright overexposed glare hotspots (>245 in V channel)
        which obscure critical packaging declarations.
        """
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        
        # High saturation/value mask
        glare_mask = cv2.inRange(v_channel, 245, 255)
        total_pixels = image_bgr.shape[0] * image_bgr.shape[1]
        glare_pixels = cv2.countNonZero(glare_mask)
        glare_ratio = glare_pixels / total_pixels
        
        is_glare = bool(glare_ratio > self.glare_threshold_ratio)
        warning = "Severe lighting glare detected on package surface; angle camera away from overhead lights." if is_glare else None
        
        return {
            "glare_ratio": round(glare_ratio, 4),
            "glare_detected": is_glare,
            "glare_warning": warning
        }

    def detect_blur(self, image_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Measures image sharpness using Laplacian variance.
        Score < 85 indicates high risk of OCR misreads.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = bool(blur_score < self.blur_laplacian_threshold)
        warning = "Image is blurry; hold camera steady and ensure packaging text is sharply in focus." if is_blurry else None
        
        return {
            "blur_score": round(blur_score, 2),
            "is_blurry": is_blurry,
            "blur_warning": warning
        }

    def detect_card_calibration(
        self,
        image_bgr: np.ndarray,
        card_type: str = "ID_1_STANDARD",
        ocr_boxes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Robust multi-strategy detection of standard reference cards (ISO/IEC 7810 ID-1:
        Aadhaar, PAN, Driving License, Voter ID, ATM/Debit Card - 85.60 x 53.98 mm, ratio ~1.586).
        Combines:
        1. Chrominance / color difference segmentation (B-R, B-G, R-G)
        2. Multi-channel Canny edge maps (B, G, R, Gray) with morphological dilation & closing
        3. Adaptive thresholding & Otsu binary maps
        4. Minimum-area rotated rectangle geometry & aspect ratio tolerance
        5. OCR semantic anchor verification (prioritizes contours overlapping Govt ID text)
        """
        h, w = image_bgr.shape[:2]
        img_area = float(h * w)

        target_meta = self.card_types.get(card_type, {
            "name": "ISO/IEC 7810 ID-1 (85.60 x 53.98 mm)",
            "width_mm": 85.60,
            "height_mm": 53.98,
            "ratio": 1.586
        })
        known_width_mm = target_meta.get("width_mm", 85.60)
        known_height_mm = target_meta.get("height_mm", 53.98)
        target_ratio = target_meta.get("ratio", 1.586)
        tolerance = getattr(self, "card_aspect_tolerance", 0.22)

        # 1. Color channel decomposition & Chrominance differences
        b, g, r = cv2.split(image_bgr)
        diff_br = cv2.absdiff(b, r)
        diff_bg = cv2.absdiff(b, g)
        diff_rg = cv2.absdiff(r, g)
        chroma = cv2.max(cv2.max(diff_br, diff_bg), diff_rg)

        # 2. Multi-channel edges across all spectral channels
        e_b = cv2.Canny(cv2.GaussianBlur(b, (5, 5), 0), 25, 75)
        e_g = cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 25, 75)
        e_r = cv2.Canny(cv2.GaussianBlur(r, (5, 5), 0), 25, 75)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blurred_gray = cv2.GaussianBlur(gray, (5, 5), 0)
        e_gray = cv2.Canny(blurred_gray, 30, 90)
        edges = cv2.bitwise_or(cv2.bitwise_or(e_b, e_g), cv2.bitwise_or(e_r, e_gray))

        # 3. Form multiple complementary binary representations
        binary_maps = []

        # Color difference threshold (isolates colored ID cards like DL/PAN from gray concrete/countertops)
        _, bin_chroma = cv2.threshold(chroma, 25, 255, cv2.THRESH_BINARY)
        binary_maps.append(("chroma", bin_chroma, 9))

        # Morphologically dilated & closed multi-channel edges (bridges broken borders & rounded corners)
        k_edge = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dil_edge = cv2.dilate(edges, k_edge)
        bin_edge_closed = cv2.morphologyEx(dil_edge, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
        binary_maps.append(("edges", bin_edge_closed, 5))

        # Otsu thresholding (for high-contrast white or metallic cards)
        _, bin_otsu = cv2.threshold(blurred_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary_maps.append(("otsu", bin_otsu, 7))
        binary_maps.append(("otsu_inv", cv2.bitwise_not(bin_otsu), 7))

        # 4. Extract OCR Card semantic anchor points if available
        id_anchor_points = []
        card_keywords = [
            "driving", "licence", "license", "aadhaar", "pan", "income tax",
            "election", "voter", "identity", "republic of india", "government of india",
            "govt of india", "bank", "debit", "credit", "union"
        ]
        if ocr_boxes:
            for box in ocr_boxes:
                text_low = (box.get("text") or "").lower()
                if any(kw in text_low for kw in card_keywords):
                    bbox = box.get("bbox")
                    if bbox and len(bbox) >= 4:
                        pts = np.array(bbox, np.float32)
                        cx_txt = float(np.mean(pts[:, 0]))
                        cy_txt = float(np.mean(pts[:, 1]))
                        id_anchor_points.append((cx_txt, cy_txt))

        candidates = []

        for name, bmap, ksize in binary_maps:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
            cleaned = cv2.morphologyEx(bmap, cv2.MORPH_CLOSE, kernel)
            cnts, _ = cv2.findContours(cleaned, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in cnts:
                area = cv2.contourArea(cnt)
                if area < img_area * 0.003 or area > img_area * 0.65:
                    continue

                rect = cv2.minAreaRect(cnt)
                (cx, cy), (rw, rh), angle = rect
                if rw == 0 or rh == 0:
                    continue

                longer = max(rw, rh)
                shorter = min(rw, rh)
                ratio = longer / shorter
                diff = abs(ratio - target_ratio)

                if diff <= tolerance:
                    rect_area = rw * rh
                    extent = area / rect_area if rect_area > 0 else 0
                    if extent > 0.58:
                        box = cv2.boxPoints(rect)
                        box_int = np.int32(box).tolist()

                        # Check if this contour encloses or is close to any ID card text
                        ocr_bonus = 0
                        for ax, ay in id_anchor_points:
                            dist = math.hypot(cx - ax, cy - ay)
                            if dist < longer:
                                ocr_bonus = 1
                                break

                        candidates.append({
                            "diff": diff,
                            "extent": extent,
                            "w_px": float(longer),
                            "h_px": float(shorter),
                            "corners": box_int,
                            "center": (cx, cy),
                            "ocr_bonus": ocr_bonus,
                            "source": name
                        })

        if candidates:
            # Sort: Prioritize OCR semantic overlap, then closest aspect ratio, then highest rectangular extent
            candidates.sort(key=lambda c: (-c["ocr_bonus"], c["diff"], -c["extent"]))
            best = candidates[0]
            best_w_px = best["w_px"]
            best_h_px = best["h_px"]
            best_quad = best["corners"]

            mm_per_pixel = known_width_mm / best_w_px
            pdp_surface_area_cm2 = round((img_area * (mm_per_pixel ** 2)) / 100.0, 2)

            return {
                "card_detected": True,
                "card_type": card_type,
                "card_name": target_meta.get("name", "ISO/IEC 7810 ID-1"),
                "card_width_mm": known_width_mm,
                "card_height_mm": known_height_mm,
                "card_width_pixels": round(best_w_px, 1),
                "card_height_pixels": round(best_h_px, 1),
                "card_corners": best_quad,
                "mm_per_pixel": round(mm_per_pixel, 5),
                "pdp_surface_area_cm2": pdp_surface_area_cm2
            }

        # Fallback estimation if physical reference card is not detected in the frame
        # Standard 150 DPI mobile macro framing (~0.18 mm/pixel)
        estimated_mm_per_pixel = 0.18
        return {
            "card_detected": False,
            "card_type": card_type,
            "card_name": target_meta.get("name", "ISO/IEC 7810 ID-1"),
            "card_width_mm": known_width_mm,
            "card_height_mm": known_height_mm,
            "card_width_pixels": None,
            "card_height_pixels": None,
            "card_corners": None,
            "mm_per_pixel": estimated_mm_per_pixel,
            "pdp_surface_area_cm2": None
        }

    def enhance_contrast_clahe(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Enhances contrast in low-light warehouse shots using CLAHE on LAB color space.
        """
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        return enhanced

    def annotate_image(
        self,
        image_bgr: np.ndarray,
        ocr_boxes: List[Dict[str, Any]],
        violations: List[Dict[str, Any]],
        card_info: Optional[Dict[str, Any]] = None,
        inspection_uuid: str = ""
    ) -> np.ndarray:
        """
        Renders legally defensible evidence annotations directly onto the image:
        - Green bounding boxes for compliant mandatory declarations
        - Red bounding boxes for non-compliant / missing declarations
        - Cyan polygon for calibrated ISO/IEC 7810 ID-1 reference card
        - Evidence timestamp & verification banner
        """
        annotated = image_bgr.copy()
        h, w, _ = annotated.shape
        
        # Draw calibration card polygon if detected
        if card_info and card_info.get("card_detected") and card_info.get("card_corners"):
            corners = np.array(card_info["card_corners"], np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [corners], True, (255, 200, 0), 3)
            top_pt = tuple(corners[0][0])
            cv2.putText(
                annotated,
                f"CALIB: ISO ID-1 CARD ({card_info.get('card_width_mm', 85.6)}x{card_info.get('card_height_mm', 53.98)}mm)",
                (max(10, top_pt[0]), max(25, top_pt[1] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 200, 0),
                2
            )

        # Draw text bounding boxes
        violated_fields = {v.get("field_key") for v in violations if v.get("field_key")}
        
        for item in ocr_boxes:
            bbox = item.get("bbox")
            field_match = item.get("field_match")
            text = item.get("text", "")
            
            if not bbox or len(bbox) < 4:
                continue
                
            pts = np.array(bbox, np.int32).reshape((-1, 1, 2))
            
            # Determine color
            if field_match in violated_fields:
                color = (0, 0, 220)  # Red for violation
                label = f"VIOLATION: {field_match}"
            elif field_match:
                color = (0, 180, 0)  # Green for compliant declaration
                label = f"OK: {field_match}"
            else:
                color = (200, 200, 200)  # Neutral light gray for other text
                label = ""

            cv2.polylines(annotated, [pts], True, color, 2)
            
            if label:
                top_left = bbox[0]
                tx, ty = int(top_left[0]), int(top_left[1])
                cv2.rectangle(annotated, (tx, max(0, ty - 22)), (tx + len(label) * 9, max(0, ty)), color, -1)
                cv2.putText(
                    annotated,
                    label,
                    (tx + 2, max(15, ty - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )

        # Add Official Inspector Watermark Header/Footer
        header_h = 40
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, header_h), (20, 20, 30), -1)
        cv2.rectangle(overlay, (0, h - 30), (w, h), (20, 20, 30), -1)
        cv2.addWeighted(overlay, 0.85, annotated, 0.15, 0, annotated)
        
        status_text = "LEGAL METROLOGY COMPLIANCE SCANNER - OFFICIAL EVIDENCE RECORD"
        cv2.putText(annotated, status_text, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        
        footer_text = f"ID: {inspection_uuid[:16]} | STATUTORY RECORD SEC 15/36 LM ACT 2009"
        cv2.putText(annotated, footer_text, (15, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        
        return annotated

cv_service = CVService()
