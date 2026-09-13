import pytest
import numpy as np
import cv2
from legal_metrology.app.services.cv_service import cv_service

def test_glare_detection():
    # Synthetic image with bright washed-out glare spot
    img = np.zeros((400, 400, 3), dtype=np.uint8) + 100
    # Add large glare patch (>10% of image area)
    img[100:300, 100:300] = 255
    
    glare_res = cv_service.detect_glare(img)
    assert glare_res["glare_detected"] is True
    assert glare_res["glare_ratio"] > 0.08
    assert "glare" in glare_res["glare_warning"].lower()

def test_blur_detection():
    # Sharp image with high frequency edges
    sharp_img = np.zeros((300, 300, 3), dtype=np.uint8)
    cv2.rectangle(sharp_img, (50, 50), (250, 250), (255, 255, 255), 5)
    cv2.line(sharp_img, (50, 50), (250, 250), (255, 255, 255), 4)
    
    sharp_res = cv_service.detect_blur(sharp_img)
    assert sharp_res["blur_score"] > 85.0
    assert sharp_res["is_blurry"] is False

    # Heavily blurred image
    blurred_img = cv2.GaussianBlur(sharp_img, (55, 55), 30)
    blur_res = cv_service.detect_blur(blurred_img)
    assert blur_res["is_blurry"] is True
    assert blur_res["blur_warning"] is not None

def test_card_calibration():
    # Synthetic image with standard ID-1 card rectangle (approx aspect ratio 1.586)
    # Width 158px, Height 100px
    card_img = np.zeros((400, 400, 3), dtype=np.uint8) + 220
    cv2.rectangle(card_img, (100, 150), (258, 250), (40, 40, 40), -1)
    cv2.rectangle(card_img, (100, 150), (258, 250), (0, 0, 0), 2)
    
    res = cv_service.detect_card_calibration(card_img, card_type="ID_1_STANDARD")
    assert "card_detected" in res
    assert "mm_per_pixel" in res
    assert res["mm_per_pixel"] > 0
    if res["card_detected"]:
        assert res["card_width_mm"] == 85.60
        assert res["pdp_surface_area_cm2"] is not None
