# LabelIQ — Integrated Field Inspection System (IFIS)

[![Smart India Hackathon 2026](https://img.shields.io/badge/SIH-2026-blue.svg)](https://www.sih.gov.in/)
[![Ministry of Consumer Affairs](https://img.shields.io/badge/Govt_of_India-Department_of_Consumer_Affairs-darkred.svg)](https://consumeraffairs.nic.in/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8.svg?logo=opencv&logoColor=white)](https://opencv.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An automated computer vision and multimodal inspection platform designed for on-site enforcement officers under the **Legal Metrology Act, 2009** and the **Legal Metrology (Packaged Commodities) Rules, 2011**. 

Engineered for **Smart India Hackathon (SIH 2026)** to address Problem Statements by the **Ministry of Consumer Affairs, Food & Public Distribution (Department of Consumer Affairs)**.

---

## 📌 Problem Context & Ground Realities

Under Section 15 of the **Legal Metrology Act, 2009**, inspecting officers must examine pre-packaged commodities across retail distribution hubs, e-commerce dark stores, and wholesale mandis. Today, manual verification presents severe operational bottlenecks:

1. **The Sub-Millimeter Measurement Barrier (Rule 7)**: Rule 7(1) Table-1 mandates minimum numeral and letter heights (1.0 mm to 6.0 mm) based on net quantity. In the field, inspectors cannot carry optical micrometers or calipers to measure fine print on flexible pouches or curved containers. Consequently, font-size compliance is rarely enforced.
2. **Multi-Panel Fragmentation ("See Base / See Back")**: FMCG manufacturers legally distribute declarations across different packaging surfaces (brand name on front, net quantity on back, batch/MRP stamped on base). Single-photo scanners misclassify these as missing declarations.
3. **Courtroom Evidence Defensibility**: Seizure memos and inspection notices often get challenged under **Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 (formerly Section 65B of the Indian Evidence Act)** due to absent cryptographic provenance, unverified coordinates, or subjective inspector notes.
4. **Connectivity Constraints in Warehouses**: Storage godowns with corrugated tin roofs frequently experience cellular dead zones, disabling cloud-only inspection tools.

---

## 💡 System Innovations & Engineering Approaches

### 1. Zero-Hardware Metric Calibration via Standard ID-1 Cards
To solve Rule 7 font-height measurement without expensive optical instruments, the system utilizes the standardized physical geometry of **ISO/IEC 7810 ID-1 cards** (.60\text{ mm} \times 53.98\text{ mm}$, aspect ratio .586$)—carried by every Indian inspector (Aadhaar, PAN, Driving License, or departmental card).

`
   Optical Scale Formula:
   mm_per_pixel = Known Card Width (85.60 mm) / Detected Card Width (pixels)
   Observed Font Height (mm) = Detected Bounding Box Height (pixels) × mm_per_pixel
`

* **Multi-Channel Contour Fusion**: Combines spectral chrominance decomposition ($|B-R|$, $|B-G|$, $|R-G|$), multi-channel Canny edge maps, and morphological closing to isolate cards on textured countertops.
* **OCR Semantic Anchors**: Prioritizes geometric contours containing strings like Government of India, Driving Licence, or Income Tax Department.
* **Sub-Millimeter Font Tier Audit**: Directly validates measured heights against the Rule 7(1) Table-1 threshold for the package's declared net weight.

### 2. Decoupled Architecture: Perception vs. Deterministic Judgment
A primary flaw in pure-LLM compliance tools is hallucination—generating non-existent penal sections or overlooking metric abbreviations. IFIS strictly decouples:
* **Perception Layer (AI / Vision)**: Multi-tier OCR (EasyOCR locally + Gemini Multimodal Vision API pool) extracts raw text strings, spatial bounding boxes, and panel associations.
* **Statutory Rule Engine (Deterministic Python)**: Hardcoded legal evaluation against codified JSON matrices. The compliance verdict (PASS, WARNING, FAIL) is mathematically computed based on gazette standards, ensuring 100% legal reliability.

### 3. Multi-Panel 360° Package Aggregation
Ingests up to 3 photographs concurrently (e.g., Front PDP, Back Label, Base Stamp). The vision engine correlates references across all panels, indexing where each statutory element was found (ound_on_panel) and eliminating false violations for multi-surface packaging.

### 4. Courtroom-Admissible Seizure Memorandum with SHA-256 Chain of Custody
Generates an official PDF memorandum under **Sections 15 & 36 of the Legal Metrology Act, 2009** via ReportLab:
* Binds hardware GPS coordinates ($\pm 3.2\text{m}$ accuracy) and satellite timestamp.
* Embeds color-coded visual evidence (Green = compliant, Red = violation, Cyan = calibration card).
* Computes an immutable composite **SHA-256 cryptographic digest** across raw image bytes and the generated PDF, establishing non-repudiation in court.

### 5. Offline-First PWA with IndexedDB Storage Queue
Field inspectors operating in concrete basements or rural warehouses can continue logging inspections without internet. Raw photos, GPS coordinates, and inspection parameters are buffered in an **IndexedDB queue (LegalMetrologyOfflineDB)** and automatically synced once a network connection is restored. A local regex parsing engine provides baseline extraction when cloud APIs are unreachable.

---

## 🏗️ Architecture & Processing Pipeline

`mermaid
flowchart TD
    A[Inspector Smartphone / PWA] -->|Hardware GPS Lock| B(Multi-Panel Image Capture + ISO ID-1 Card)
    B --> C{CV Pre-Processing Engine}
    C -->|Glare Check: HSV V > 245| D[Quality Filter]
    C -->|Blur Check: Laplacian Var < 85| D
    C -->|LAB CLAHE Enhancement| E[Contrast Optimized Images]
    E --> F[ISO ID-1 Reference Card Calibration]
    F -->|Derives mm/px & PDP Area| G[Spatial Metric Scale]
    E --> H{Dual-Tier Perception Pipeline}
    H -->|Tier 1: Edge Extraction| I[Local EasyOCR Bounding Boxes]
    H -->|Tier 2: Multimodal Reasoning| J[Gemini Vision Pool Multi-Panel Pass]
    H -->|Tier 3: Offline Warehouse Mode| K[Deterministic Statutory Regex Engine]
    I & J & K --> L[Aggregated Entity Extraction]
    G & L --> M[Deterministic Statutory Rule Engine]
    M -->|Rule 6: Mandatory Fields| N[Compliance Evaluation]
    M -->|Rule 7: Font Height Check| N
    M -->|Rule 12: Metric Units Check| N
    N --> O[Human-in-the-Loop Review Screen]
    O -->|Inspector Verified / Overridden| P[Final Compliance Verdict]
    P --> Q[ReportLab Legal Seizure Memo PDF]
    P --> R[SHA-256 Cryptographic Evidence Stamp]
    P --> S[SQLite Database & Directorate Admin Registry]
`

---

## 📂 Project Structure

`
legal_metrology_project/
├── docs/
│   └── resources/                       # Official Gazette & Statutory References
│       └── Legal_Metrology_Packaged_Commodities_Rules_2011.pdf
├── legal_metrology/
│   ├── app/
│   │   ├── rules/                       # Statutory rule books codified in JSON
│   │   │   ├── base_rules.json          # Core LMPC Rules 2011 (Rule 6, 7, 12)
│   │   │   ├── food.json                # FSSAI Packaging Regulations 2011
│   │   │   ├── cosmetics.json           # CDSCO Cosmetics Rules 2020
│   │   │   ├── electronics.json         # MeitY Compulsory Registration & BIS
│   │   │   └── general.json             # General packaged commodity defaults
│   │   ├── services/                    # Core business logic & CV algorithms
│   │   │   ├── cv_service.py            # Card detection, GLARE/blur, CLAHE
│   │   │   ├── ocr_service.py           # EasyOCR box extraction & text stitching
│   │   │   ├── llm_service.py           # Gemini multimodal vision & regex engine
│   │   │   ├── rule_engine.py           # Deterministic legal verification & font scale
│   │   │   ├── inspection_service.py    # Pipeline orchestrator & correction handler
│   │   │   ├── pdf_service.py           # Courtroom seizure memo generator (SHA-256)
│   │   │   └── sample_generator.py      # Synthetic benchmark sample generator
│   │   ├── static/                      # Frontend presentation layer
│   │   │   ├── css/styles.css           # Department of Consumer Affairs styling
│   │   │   └── js/
│   │   │       ├── app.js               # Multi-screen SPA controller
│   │   │       ├── correction.js        # Interactive canvas & OCR correction
│   │   │       └── offline_store.js     # IndexedDB offline synchronization queue
│   │   ├── templates/                   # HTML5 responsive templates
│   │   │   ├── index.html               # Main 5-in-1 inspection portal
│   │   │   ├── correction.html          # Split-view OCR canvas correction tool
│   │   │   └── dashboard.html           # Historical enforcement ledger
│   │   ├── config.py                    # Environment settings, thresholds, ID-1 specs
│   │   ├── database.py                  # SQLAlchemy engine & session management
│   │   ├── main.py                      # FastAPI REST application & routing
│   │   ├── models.py                    # SQLite ORM models (Inspections, Violations)
│   │   └── schemas.py                   # Pydantic validation schemas
│   ├── samples/                         # Multi-panel reference packaging assets
│   └── tests/                           # Pytest regression and unit test suites
│       ├── test_api.py                  # REST endpoint integration tests
│       ├── test_cv.py                   # CV glare, blur, and ID-1 card tests
│       ├── test_ocr_and_rules.py        # Rule engine & font-size compliance tests
│       └── test_pdf_generation.py       # PDF layout & SHA-256 verification tests
├── run_server.py                        # Root server launcher
├── requirements.txt                     # Pinned project dependencies
├── .env.example                         # Environment configuration template
└── .gitignore                           # Git ignore rules for databases, keys & cache
`

---

## ⚖️ Statutory Coverage Matrix

| Statutory Clause | Mandatory Declaration | Verification Mechanism | Penalty Section |
| :--- | :--- | :--- | :--- |
| **Rule 6(1)(a)** | Manufacturer / Packer / Importer Address | Street address, state & 6-digit PIN validation | Sec. 36(1) LM Act 2009 |
| **Rule 6(1)(b)** | Common or Generic Name | Commodity designation on Principal Display Panel | Sec. 36(1) LM Act 2009 |
| **Rule 6(1)(c)** | Net Quantity in Metric Units | Standard SI units (, kg, ml, l, N, U$) under Rule 12 | Sec. 36(1) & Rule 12 |
| **Rule 6(1)(d)** | Month & Year of Manufacture / Packing | Regex verification of /YYYY$ or \ YYYY$ | Sec. 36(1) LM Act 2009 |
| **Rule 6(1)(e)** | Maximum Retail Price (MRP) | Mandatory price declaration with (incl. of all taxes) | Sec. 36(1) LM Act 2009 |
| **Rule 6(1)(s)** | Unit Sale Price (USP) | Pro-rata rate per  / ml / piece$ (mandatory since 2021) | Sec. 36(1) LM Act 2009 |
| **Rule 6(1)(n)** | Consumer Care Cell | Helpline number and email contact verification | Sec. 36(1) LM Act 2009 |
| **Rule 7 Table-1** | Minimum Font Size (Numeral & Letter) | ID-1 pixel-to-mm ratio vs. net weight tier | Rule 7(1) Schedule II |
| **FSSAI Reg. 2.2.1** | Food License & Dietary Symbol | 14-digit FSSAI number and Veg (Green) / Non-Veg (Brown) | Sec. 58 FSS Act 2006 |
| **CDSCO Rule 34** | Cosmetic License & Batch Traceability | Manufacturing license number (M.L.) & Batch/Lot ID | Drugs & Cosmetics Act |
| **MeitY CRO 2021** | BIS Compulsory Registration Scheme | R-XXXXXXXX registration format & IS standards | BIS Act, 2016 |

---

## 📚 Official Statutory References & Gazette

The official statutory gazettes and regulatory frameworks enforced by this platform are bundled in the repository:
* [📄 Legal Metrology (Packaged Commodities) Rules, 2011 (Official Gazette PDF)](docs/resources/Legal_Metrology_Packaged_Commodities_Rules_2011.pdf)

---

## 🚀 Quickstart & Installation

### Prerequisites
* Python 3.11, 3.12, or 3.14
* Git

### 1. Clone Repository
`ash
git clone https://github.com/abhilasheggadi/LabellQ.git
cd LabellQ
`

### 2. Create Virtual Environment
`ash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
`

### 3. Install Dependencies
`ash
pip install --upgrade pip
pip install -r requirements.txt
`

### 4. Configure Environment Variables
Copy .env.example to .env and specify your Gemini API key (optional for offline regex mode, required for multimodal vision):
`ash
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
`
Edit .env:
`nv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3-flash-preview
PORT=8000
`

### 5. Launch the Server
`ash
python run_server.py
`
Open your browser and navigate to: **http://127.0.0.1:8000**

---

## 🧪 Running Automated Tests

Run the complete regression suite covering computer vision algorithms, deterministic rule matching, font-size calculations, and ReportLab PDF synthesis:

`ash
# Run all unit tests
python -m pytest legal_metrology/tests/test_cv.py legal_metrology/tests/test_ocr_and_rules.py legal_metrology/tests/test_pdf_generation.py -v
`

---

## 👥 Built by Engineering Students for SIH 2026

* **Competition**: Smart India Hackathon (SIH 2026)
* **Nodal Ministry**: Ministry of Consumer Affairs, Food & Public Distribution
* **Department**: Directorate of Legal Metrology (Weights & Measures Division)
* **Design Philosophy**: High robustness in field conditions, zero legal hallucination, and tamper-proof evidence provenance.
