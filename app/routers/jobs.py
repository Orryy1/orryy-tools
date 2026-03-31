"""Job polling router - check status of async jobs."""

import logging
from fastapi import APIRouter, HTTPException

from app.models import JobResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_jobs_store():
    """Get the shared jobs store from the stems router."""
    from app.routers.stems import jobs_store
    return jobs_store


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Poll the status of an async job.

    Status values:
    - pending: Job is queued
    - processing: Job is running
    - complete: Job finished successfully (result field has data)
    - failed: Job failed (error field has details)
    """
    jobs_store = _get_jobs_store()
    job = jobs_store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        job_type=job.job_type,
        result=job.result,
        error=job.error,
        progress=job.progress,
    )
