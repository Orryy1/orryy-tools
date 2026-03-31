"""Weekly MixFeed pipeline - curates and sends a weekly newsletter of top mixes."""

import logging
from datetime import datetime, timezone

from app.services.youtube_client import youtube_client
from app.services.anthropic_client import anthropic_client
from app.services.buttondown_client import buttondown_client

logger = logging.getLogger(__name__)

# Channels to monitor for new mixes (add channel IDs here)
MONITORED_CHANNELS = [
    # Add channel IDs of DJ/music channels to aggregate from
]


async def run_mixfeed_pipeline() -> None:
    """Weekly MixFeed cron job.

    1. Scans monitored YouTube channels for new uploads this week.
    2. Generates a curated newsletter section via Claude.
    3. Creates a draft email on Buttondown.
    """
    logger.info("MixFeed pipeline starting...")

    all_videos = []
    for channel_id in MONITORED_CHANNELS:
        try:
            channel = await youtube_client.get_channel_by_id(channel_id)
            uploads_id = channel.get("uploads_playlist_id", "")
            if uploads_id:
                videos = await youtube_client.get_recent_videos(uploads_id, max_results=5)
                for v in videos:
                    v["channel_title"] = channel.get("title", "Unknown")
                all_videos.extend(videos)
        except Exception as e:
            logger.error(f"Failed to fetch videos for channel {channel_id}: {e}")

    if not all_videos:
        logger.info("MixFeed: No new videos found across monitored channels, skipping.")
        return

    # Sort by view count descending to surface the most popular
    all_videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)
    top_videos = all_videos[:10]

    # Build track list for Claude
    tracks = [
        {
            "title": v.get("title", "Untitled"),
            "artist": v.get("channel_title", "Unknown"),
            "bpm": "?",
            "key": "?",
        }
        for v in top_videos
    ]

    # Generate newsletter content
    try:
        newsletter_html = await anthropic_client.generate_newsletter_section(
            topic="This Week's Hottest Mixes",
            tracks=tracks,
            context=f"Week of {datetime.now(timezone.utc).strftime('%d %B %Y')}. "
                    "These are the most-watched new DJ mixes and music uploads from channels we follow.",
        )
    except Exception as e:
        logger.error(f"MixFeed: Failed to generate newsletter content: {e}")
        return

    # Create draft on Buttondown
    week_str = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"MixFeed Weekly - {week_str}"

    try:
        result = await buttondown_client.send_email(
            subject=subject,
            body=newsletter_html,
            status="draft",
        )
        logger.info(f"MixFeed draft created: {result.get('id')}")
    except Exception as e:
        logger.error(f"MixFeed: Failed to create Buttondown draft: {e}")

    logger.info("MixFeed pipeline complete.")
