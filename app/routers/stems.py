"""Stem separation router - async job-based stem splitting via Replicate."""

import logging
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import Job, JobStatus, StemJobCreated
from app.services.stems import run_stem_separation

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store (shared with jobs router)
# Import this from a shared location in production; for now, module-level dict
jobs_store: dict[str, Job] = {}


def get_jobs_store() -> dict[str, Job]:
    """Get the shared jobs store reference."""
    return jobs_store


@router.post("/stems", response_model=StemJobCreated)
async def start_stem_separation(file: UploadFile = File(...)):
    """Upload an audio file to start async stem separation.

    Returns a job_id that can be polled via GET /api/jobs/{job_id}.
    Stems are separated into: vocals, drums, bass, other.
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

        # 100MB limit for stem separation
        if len(file_bytes) > 100 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 100MB.")

        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, status=JobStatus.PENDING, job_type="stems")
        jobs_store[job_id] = job

        # Start background task
        asyncio.create_task(
            run_stem_separation(file_bytes, file.filename, job_id, jobs_store)
        )

        logger.info(f"Stem separation job created: {job_id}")
        return StemJobCreated(job_id=job_id, status=JobStatus.PENDING)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start stem separation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start stem separation: {str(e)}")
