import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from ..config import settings

def generate_sample_images():
    samples_dir = settings.SAMPLES_DIR
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1. Compliant Food Label
    img1 = Image.new("RGB", (700, 500), color="#FAF6F0")
    draw = ImageDraw.Draw(img1)
    
    # Border & Banner
    draw.rectangle([(20, 20), (680, 480)], outline="#2D3748", width=3)
    draw.rectangle([(20, 20), (680, 75)], fill="#1E3A8A")
    draw.text((35, 30), "NUTRI-CRUNCH WHOLE WHEAT BISCUITS", fill="#FFFFFF")
    draw.text((35, 52), "Generic Name: Biscuits / Baked Cookies", fill="#93C5FD")
    
    # Mandatory Declarations
    draw.text((40, 95), "Net Quantity: 200 g", fill="#111827")
    draw.text((40, 125), "MRP: Rs. 40.00 (incl. of all taxes)", fill="#111827")
    draw.text((40, 155), "Unit Sale Price: Rs. 0.20 / g", fill="#111827")
    draw.text((40, 185), "Mfg Date: 08/2026", fill="#111827")
    draw.text((40, 215), "Best Before: 6 months from manufacture", fill="#111827")
    draw.text((40, 245), "Manufactured By: Sunrise Foods Pvt. Ltd., Plot 12, Industrial Area, Pune 411001", fill="#111827")
    draw.text((40, 275), "Country of Origin: Made in India", fill="#111827")
    draw.text((40, 305), "Consumer Care: care@sunrisefoods.in | Tel: 1800-200-4567", fill="#111827")
    draw.text((40, 335), "FSSAI Lic. No.: 10019022009876", fill="#111827")
    draw.text((40, 365), "Ingredients: Whole Wheat Flour (65%), Sugar, Edible Veg Oil, Salt, Raising Agents", fill="#4B5563")

    # Veg Logo (Green circle inside green square)
    draw.rectangle([(600, 95), (645, 140)], outline="#16A34A", width=3)
    draw.ellipse([(610, 105), (635, 130)], fill="#16A34A")
    draw.text((585, 145), "100% VEG", fill="#16A34A")

    # Save
    p1 = samples_dir / "sample_food_compliant.jpg"
    img1.save(p1, quality=95)

    # 2. Non-Compliant Food Label (Missing Veg symbol, No taxes clause on MRP, Missing USP)
    img2 = Image.new("RGB", (700, 500), color="#FFFBEB")
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([(20, 20), (680, 480)], outline="#991B1B", width=3)
    draw2.rectangle([(20, 20), (680, 75)], fill="#991B1B")
    draw2.text((35, 30), "CHEF SPECIAL MASALA NOODLES", fill="#FFFFFF")
    draw2.text((35, 52), "Instant Noodles with Seasoning", fill="#FECACA")
    
    draw2.text((40, 100), "Net Quantity: 150 g", fill="#111827")
    draw2.text((40, 135), "MRP: Rs. 35", fill="#111827")  # VIOLATION: Missing (incl. of all taxes)
    draw2.text((40, 170), "Mfg Date: 05/2026", fill="#111827")
    draw2.text((40, 205), "Best Before: 12/2026", fill="#111827")
    draw2.text((40, 240), "Packed By: Apex Agro Ltd., Sector 5, Haridwar", fill="#111827")
    draw2.text((40, 275), "Made in India", fill="#111827")
    draw2.text((40, 310), "Consumer Care: +91-9876543210", fill="#111827")
    draw2.text((40, 345), "FSSAI Lic. No.: 12345", fill="#111827")  # VIOLATION: Short license number (not 14 digits)
    # VIOLATION: Veg logo omitted, USP omitted
    
    p2 = samples_dir / "sample_food_violation.jpg"
    img2.save(p2, quality=95)

    # 3. Cosmetics Label (Non-Compliant: Missing M.L. No & Batch No)
    img3 = Image.new("RGB", (700, 500), color="#FDF2F8")
    draw3 = ImageDraw.Draw(img3)
    draw3.rectangle([(20, 20), (680, 480)], outline="#831843", width=3)
    draw3.rectangle([(20, 20), (680, 75)], fill="#831843")
    draw3.text((35, 30), "GLOW-RADIANCE HYDRATING FACE SERUM", fill="#FFFFFF")
    draw3.text((35, 52), "Generic Name: Cosmetic Skin Care Serum", fill="#FBCFE8")
    
    draw3.text((40, 100), "Net Volume: 30 ml", fill="#111827")
    draw3.text((40, 135), "MRP: Rs. 499.00 (inclusive of all taxes)", fill="#111827")
    draw3.text((40, 170), "Unit Sale Price: Rs. 16.63 / ml", fill="#111827")
    draw3.text((40, 205), "Mfg Date: 02/2026", fill="#111827")
    draw3.text((40, 240), "Use Before: 02/2028", fill="#111827")
    draw3.text((40, 275), "Mfg by: Luxe Botanicals Ltd., Andheri East, Mumbai 400069", fill="#111827")
    draw3.text((40, 310), "Country of Origin: Made in India", fill="#111827")
    draw3.text((40, 345), "Customer Care: help@luxebotanicals.com | Tel: 022-28345678", fill="#111827")
    # VIOLATION: Missing M.L. No. (Manufacturing License) & B.No. (Batch Number)
    
    p3 = samples_dir / "sample_cosmetics_violation.jpg"
    img3.save(p3, quality=95)

    # 4. Electronics Charger (Compliant with BIS CRS R-41234567 & Coin)
    img4 = Image.new("RGB", (800, 550), color="#F8FAFC")
    draw4 = ImageDraw.Draw(img4)
    draw4.rectangle([(20, 20), (780, 530)], outline="#0F172A", width=3)
    draw4.rectangle([(20, 20), (780, 75)], fill="#0F172A")
    draw4.text((35, 30), "SUPERCHARGE 65W DUAL-PORT GaN ADAPTER", fill="#FFFFFF")
    draw4.text((35, 52), "Generic Name: Power Adapter / Battery Charger", fill="#94A3B8")

    draw4.text((40, 95), "Model No.: SC-65-GAN", fill="#111827")
    draw4.text((40, 125), "Electrical Rating: Input 100-240V ~ 50/60Hz 1.5A | Output 65W Max", fill="#111827")
    draw4.text((40, 155), "Net Quantity: 1 N (1 Piece)", fill="#111827")
    draw4.text((40, 185), "MRP: Rs. 1499.00 (incl. of all taxes)", fill="#111827")
    draw4.text((40, 215), "Unit Sale Price: Rs. 1499.00 / piece", fill="#111827")
    draw4.text((40, 245), "Mfg Date: 07/2026", fill="#111827")
    draw4.text((40, 275), "Imported & Marketed By: VoltTech India Pvt. Ltd., Tech Zone, Bangalore 560100", fill="#111827")
    draw4.text((40, 305), "Country of Origin: Made in India", fill="#111827")
    draw4.text((40, 335), "Customer Care: support@volttech.in | 1800-419-9999", fill="#111827")
    draw4.text((40, 365), "BIS CRS Registration: R-41234567 (IS 13252 Part 1)", fill="#111827")
    draw4.text((40, 395), "E-Waste Compliance: Do not dispose with household waste. Recycle responsibly.", fill="#4B5563")

    # Draw Calibrated INR 1 Coin on the right side
    coin_cx, coin_cy, coin_r = 690, 220, 60
    draw4.ellipse([(coin_cx - coin_r, coin_cy - coin_r), (coin_cx + coin_r, coin_cy + coin_r)], fill="#CBD5E1", outline="#475569", width=4)
    draw4.ellipse([(coin_cx - coin_r + 8, coin_cy - coin_r + 8), (coin_cx + coin_r - 8, coin_cy + coin_r - 8)], outline="#64748B", width=2)
    draw4.text((coin_cx - 25, coin_cy - 18), "Rs. 1", fill="#1E293B")
    draw4.text((coin_cx - 30, coin_cy + 5), "INDIA", fill="#475569")

    p4 = samples_dir / "sample_electronics_compliant.jpg"
    img4.save(p4, quality=95)

    return [str(p1), str(p2), str(p3), str(p4)]

if __name__ == "__main__":
    generate_sample_images()
