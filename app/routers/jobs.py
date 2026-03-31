"""Job polling router - check status of async jobs."""

import logging
from fastapi import APIRouter, HTTPException

from app.models import JobResponse
from app.jobs.store import job_store

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
    # Check in-memory store first (stems jobs)
    jobs_store_mem = _get_jobs_store()
    job = jobs_store_mem.get(job_id)

    if job:
        return JobResponse(
            job_id=job.job_id,
            status=job.status,
            job_type=job.job_type,
            result=job.result,
            error=job.error,
            progress=job.progress,
        )

    # Check SQLite store (mashup and other jobs)
    db_job = await job_store.get_job(job_id)
    if db_job:
        return JobResponse(
            job_id=db_job["job_id"],
            status=db_job["status"],
            job_type=db_job.get("job_type", ""),
            result=db_job.get("result"),
            error=db_job.get("error"),
            progress=db_job.get("progress"),
        )

    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
