"""Track identification router - identify tracks via AcoustID."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import TrackIDResult
from app.services.trackid import identify_track

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trackid", response_model=TrackIDResult)
async def identify_track_endpoint(file: UploadFile = File(...)):
    """Upload an audio file and identify the track using AcoustID/Chromaprint.

    Returns artist, title, album, and release date if a match is found.
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

        if len(file_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

        result = await identify_track(file_bytes, filename=file.filename)
        return TrackIDResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Track identification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Track identification failed: {str(e)}")
