import uvicorn
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Legal Metrology Compliance Scanner on http://127.0.0.1:{port}")
    uvicorn.run("legal_metrology.app.main:app", host="0.0.0.0", port=port, reload=False)
