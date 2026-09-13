import logging
import numpy as np
from typing import List, Dict, Any, Tuple
import torch

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        self._reader = None
        self.gpu_available = torch.cuda.is_available()

    @property
    def reader(self):
        """Lazy load EasyOCR reader to save startup time and memory."""
        if self._reader is None:
            try:
                import easyocr
                logger.info(f"Initializing EasyOCR reader (GPU={self.gpu_available})...")
                self._reader = easyocr.Reader(['en'], gpu=self.gpu_available, verbose=False)
            except Exception as e:
                logger.error(f"Failed to load EasyOCR: {e}")
                self._reader = None
        return self._reader

    def extract_text_with_boxes(self, image_bgr: np.ndarray, image_index: int = 0) -> List[Dict[str, Any]]:
        """
        Runs OCR on the given BGR image.
        Returns a list of dicts with bounding boxes and image_index.
        """
        results = []
        if self.reader is not None:
            try:
                # EasyOCR expects RGB or image path / numpy array
                rgb_img = image_bgr[:, :, ::-1]
                ocr_out = self.reader.readtext(rgb_img)
                for bbox, text, conf in ocr_out:
                    # Convert bbox coords to float list
                    box_pts = [[float(pt[0]), float(pt[1])] for pt in bbox]
                    xs = [pt[0] for pt in box_pts]
                    ys = [pt[1] for pt in box_pts]
                    h_px = max(ys) - min(ys)
                    w_px = max(xs) - min(xs)
                    
                    results.append({
                        "text": text.strip(),
                        "confidence": round(float(conf), 3),
                        "bbox": box_pts,
                        "height_px": round(h_px, 2),
                        "width_px": round(w_px, 2),
                        "image_index": image_index
                    })
                return results
            except Exception as e:
                logger.error(f"EasyOCR extraction failed: {e}")

        # Fallback basic text parser if easyocr fails
        return results

    def get_full_text(self, ocr_results: List[Dict[str, Any]]) -> str:
        """Joins all extracted text blocks chronologically."""
        return "\n".join([item["text"] for item in ocr_results if item.get("text")])

ocr_service = OCRService()
