"""Audio analysis router - key, BPM, energy detection."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import AnalysisResult
from app.services.audio import analyze_audio_file

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_track(file: UploadFile = File(...)):
    """Upload an audio file and get key, BPM, energy, and duration analysis.

    Accepts MP3, WAV, FLAC, and OGG files.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_extensions)}",
        )

    try:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # 50MB limit
        if len(file_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

        result = await analyze_audio_file(file_bytes, filename=file.filename)
        return AnalysisResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
