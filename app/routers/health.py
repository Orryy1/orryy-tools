"""Health check router."""

from fastapi import APIRouter

from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Railway and uptime monitoring.

    Returns:
        JSON with status "ok" and the current API version.
    """
    return HealthResponse(status="ok", version="1.0.0")
