"""
OCR Service — FastAPI backend
Endpoints:
  POST /ocr/extract        Upload an image, get structured fields + confidence scores
  POST /ocr/correct        Submit human corrections → persisted to memory.json
  GET  /ocr/memory         Retrieve full correction dictionary
  DELETE /ocr/memory       Clear all learned corrections
  GET  /health             Liveness check

Serves the frontend SPA from /
"""

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from memory import CorrectionMemory
from models import CorrectRequest, CorrectResponse, ExtractResponse, MemoryResponse
from ocr_engine import OCREngine

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(
    title="OCR Service API",
    version="1.0.0",
    description="Self-correcting OCR with persistent human-in-the-loop correction memory.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = OCREngine()
mem = CorrectionMemory()

ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif",
    "image/webp", "image/tiff", "application/pdf",
}
MAX_SIZE_MB = 20


# ------------------------------------------------------------------ #
#  Frontend
# ------------------------------------------------------------------ #

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


# ------------------------------------------------------------------ #
#  OCR routes
# ------------------------------------------------------------------ #

@app.get("/health")
def health():
    return {"status": "ok", "engine": engine.engine_name}


@app.post("/ocr/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)):
    """
    Upload an image or PDF. Returns extracted fields with per-field
    confidence scores. Memory corrections are applied automatically
    before returning.
    """
    # Validate size
    data = await file.read()
    if len(data) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_SIZE_MB} MB limit.")

    # Validate type (by declared content-type; Tesseract/PIL will catch corrupt files)
    ct = (file.content_type or "").lower()
    if ct and ct not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type: {ct}")

    try:
        fields = engine.extract(data, file.filename or "document")
    except Exception as exc:
        raise HTTPException(422, f"Extraction failed: {exc}") from exc

    # Apply correction memory
    for f in fields:
        corrected = mem.apply(f["raw_value"])
        if corrected != f["raw_value"]:
            f["display_value"] = corrected
            f["memory_corrected"] = True

    return ExtractResponse(
        fields=fields,
        filename=file.filename or "document",
        engine_used=engine.engine_name,
    )


@app.post("/ocr/correct", response_model=CorrectResponse)
def correct(req: CorrectRequest):
    """
    Persist human corrections to the correction dictionary.
    Each correction is a raw OCR string → verified correct string mapping.
    """
    new_count = mem.add_batch(req.corrections)
    return CorrectResponse(
        status="ok",
        new_entries=new_count,
        total_entries=len(mem.get_all()),
    )


@app.get("/ocr/memory", response_model=MemoryResponse)
def get_memory():
    """Return the full correction dictionary."""
    data = mem.get_all()
    return MemoryResponse(corrections=data, count=len(data))


@app.delete("/ocr/memory")
def clear_memory():
    """Wipe all learned corrections."""
    mem.clear()
    return {"status": "cleared"}


# ------------------------------------------------------------------ #
#  Entry point
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
