"""Mashup generation router - create mashup previews via Modal."""

import logging
import uuid
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import Job, JobStatus
from app.jobs.store import job_store
from app.services.modal_client import modal_client
from app.services.storage import upload_file_to_r2, generate_presigned_url

logger = logging.getLogger(__name__)
router = APIRouter()


class MashupRequest(BaseModel):
    track_a_url: str = Field(..., description="Presigned URL or public URL for track A")
    track_b_url: str = Field(..., description="Presigned URL or public URL for track B")
    target_bpm: float = Field(..., description="Target BPM for the mashup", ge=60, le=200)
    target_key: str = Field(..., description="Target musical key (e.g. 'C major')")
    preview_duration: float = Field(default=30.0, description="Preview duration in seconds", ge=5, le=120)


class MashupJobResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str = "Mashup generation started"


async def _run_mashup(job_id: str, request: MashupRequest) -> None:
    """Background task to generate a mashup via Modal and upload the result."""
    try:
        await job_store.update_job(job_id, status="processing", progress=0.1)

        # Call Modal function
        wav_bytes = await modal_client.call_mashup(
            track_a_url=request.track_a_url,
            track_b_url=request.track_b_url,
            target_bpm=request.target_bpm,
            target_key=request.target_key,
            preview_duration=request.preview_duration,
        )

        await job_store.update_job(job_id, progress=0.8)

        # Upload result to R2
        r2_key = f"mashups/{job_id}/preview.wav"
        await upload_file_to_r2(wav_bytes, r2_key, content_type="audio/wav")
        download_url = await generate_presigned_url(r2_key, expires_in=86400)

        await job_store.update_job(
            job_id,
            status="complete",
            progress=1.0,
            result={
                "download_url": download_url,
                "duration": request.preview_duration,
                "target_bpm": request.target_bpm,
                "target_key": request.target_key,
                "size_bytes": len(wav_bytes),
            },
        )
        logger.info(f"Mashup complete for job {job_id}: {len(wav_bytes)} bytes")

    except Exception as e:
        logger.error(f"Mashup failed for job {job_id}: {e}", exc_info=True)
        await job_store.update_job(job_id, status="failed", error=str(e))


@router.post("/mashup", response_model=MashupJobResponse)
async def create_mashup(request: MashupRequest):
    """Start an async mashup generation job.

    Provide URLs for two tracks, a target BPM, and target key.
    The mashup is generated on Modal's GPU infrastructure and uploaded to R2.
    Poll GET /api/jobs/{job_id} for status and download URL.
    """
    if not request.track_a_url or not request.track_b_url:
        raise HTTPException(status_code=400, detail="Both track URLs are required")

    job_id = str(uuid.uuid4())
    await job_store.create_job(job_id, job_type="mashup")

    asyncio.create_task(_run_mashup(job_id, request))

    logger.info(f"Mashup job created: {job_id}")
    return MashupJobResponse(job_id=job_id)
