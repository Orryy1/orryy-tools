from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


# --- Job System ---

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    job_type: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[float] = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    job_type: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[float] = None


# --- Audio Analysis ---

class AnalysisResult(BaseModel):
    key: str = Field(..., description="Musical key (e.g. 'C major', 'A minor')")
    bpm: float = Field(..., description="Beats per minute")
    energy: float = Field(..., description="Average RMS energy (0-1 normalized)")
    duration: float = Field(..., description="Track duration in seconds")
    filename: str = ""


# --- Stem Separation ---

class StemJobCreated(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    message: str = "Stem separation started"


class StemResult(BaseModel):
    vocals: str = Field(..., description="Download URL for vocals stem")
    drums: str = Field(..., description="Download URL for drums stem")
    bass: str = Field(..., description="Download URL for bass stem")
    other: str = Field(..., description="Download URL for other stem")


# --- Compatibility ---

class TrackInfo(BaseModel):
    key: str
    bpm: float
    energy: float
    duration: float
    filename: str = ""


class CompatibilityResult(BaseModel):
    score: float = Field(..., description="Overall compatibility score 0-100")
    key_compatibility: float = Field(..., description="Key compatibility score 0-100")
    bpm_compatibility: float = Field(..., description="BPM compatibility score 0-100")
    energy_compatibility: float = Field(..., description="Energy compatibility score 0-100")
    recommendation: str = Field(..., description="Human-readable recommendation")
    track_a: TrackInfo
    track_b: TrackInfo


# --- Track Identification ---

class TrackIDResult(BaseModel):
    identified: bool = False
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    release_date: Optional[str] = None
    score: Optional[float] = None
    acoustid: Optional[str] = None
    recordings: Optional[List[Dict[str, Any]]] = None


# --- Billing ---

class CheckoutRequest(BaseModel):
    price_id: str = Field(..., description="Stripe price ID")
    success_url: str = Field(default="https://tools.orryy.com/success")
    cancel_url: str = Field(default="https://tools.orryy.com/cancel")
    customer_email: Optional[str] = None
    customer_id: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionStatus(BaseModel):
    customer_id: str
    is_active: bool = False
    plan: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False


# --- Generic ---

class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
