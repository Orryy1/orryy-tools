"""Job status models for the SQLite-backed job store."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class JobRecord(BaseModel):
    """Full job record as stored in SQLite."""
    job_id: str
    job_type: str = ""
    status: JobStatusEnum = JobStatusEnum.PENDING
    progress: Optional[float] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class JobCreate(BaseModel):
    """Input for creating a new job."""
    job_id: str
    job_type: str = ""


class JobUpdate(BaseModel):
    """Input for updating a job."""
    status: Optional[str] = None
    progress: Optional[float] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
