"""TuneBot router - YouTube channel audits powered by YouTube Data API + Claude."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.youtube_client import youtube_client
from app.services.anthropic_client import anthropic_client

logger = logging.getLogger(__name__)
router = APIRouter()


class AuditRequest(BaseModel):
    channel_id: Optional[str] = Field(default=None, description="YouTube channel ID (UCxxxx)")
    handle: Optional[str] = Field(default=None, description="YouTube handle (@username)")


class AuditResponse(BaseModel):
    channel_title: str
    channel_id: str
    subscriber_count: int
    video_count: int
    view_count: int
    recent_videos_analyzed: int
    audit_report: str


@router.post("/tunebot/audit", response_model=AuditResponse)
async def channel_audit(request: AuditRequest):
    """Run a full YouTube channel audit.

    Provide either a channel_id (UCxxxx) or a handle (@username).
    Returns channel stats and an AI-generated audit report with
    actionable growth recommendations.
    """
    if not request.channel_id and not request.handle:
        raise HTTPException(
            status_code=400,
            detail="Provide either channel_id or handle",
        )

    try:
        # Fetch channel data
        if request.channel_id:
            channel_data = await youtube_client.get_channel_by_id(request.channel_id)
        else:
            channel_data = await youtube_client.get_channel_by_handle(request.handle)

        # Fetch recent videos
        uploads_id = channel_data.get("uploads_playlist_id", "")
        videos = []
        if uploads_id:
            videos = await youtube_client.get_recent_videos(uploads_id, max_results=10)

        # Generate audit report via Claude
        audit_report = await anthropic_client.generate_channel_audit(channel_data, videos)

        return AuditResponse(
            channel_title=channel_data["title"],
            channel_id=channel_data["channel_id"],
            subscriber_count=channel_data["subscriber_count"],
            video_count=channel_data["video_count"],
            view_count=channel_data["view_count"],
            recent_videos_analyzed=len(videos),
            audit_report=audit_report,
        )

    except ValueError as e:
        logger.warning(f"Channel audit validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Channel audit failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Channel audit failed: {str(e)}")
