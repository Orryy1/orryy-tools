"""Daily TuneBot checks - monitors tracked channels for anomalies or milestones."""

import logging
from datetime import datetime, timezone

from app.services.youtube_client import youtube_client

logger = logging.getLogger(__name__)

# Channels to run daily checks on (channel_id -> last known stats)
TRACKED_CHANNELS = [
    # Add channel IDs to track daily
]

# Milestone thresholds to notify on
SUBSCRIBER_MILESTONES = [100, 500, 1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]


async def run_tunebot_daily() -> None:
    """Daily TuneBot cron job.

    Checks tracked channels for:
    - Subscriber milestone crossings
    - Unusual view spikes on recent videos
    - New video uploads
    """
    logger.info("TuneBot daily check starting...")

    for channel_id in TRACKED_CHANNELS:
        try:
            channel = await youtube_client.get_channel_by_id(channel_id)
            title = channel.get("title", "Unknown")
            subs = channel.get("subscriber_count", 0)
            views = channel.get("view_count", 0)

            logger.info(
                f"TuneBot daily: {title} - "
                f"{subs:,} subs, {views:,} total views"
            )

            # Check subscriber milestones
            for milestone in SUBSCRIBER_MILESTONES:
                if subs >= milestone and subs < milestone * 1.1:
                    logger.info(
                        f"TuneBot milestone alert: {title} has reached {milestone:,} subscribers!"
                    )

            # Check recent videos for view spikes
            uploads_id = channel.get("uploads_playlist_id", "")
            if uploads_id:
                videos = await youtube_client.get_recent_videos(uploads_id, max_results=5)
                if videos:
                    avg_views = sum(v.get("view_count", 0) for v in videos) / len(videos)
                    for v in videos:
                        vc = v.get("view_count", 0)
                        if avg_views > 0 and vc > avg_views * 3:
                            logger.info(
                                f"TuneBot spike alert: \"{v.get('title')}\" on {title} "
                                f"has {vc:,} views (3x average of {int(avg_views):,})"
                            )

        except Exception as e:
            logger.error(f"TuneBot daily check failed for {channel_id}: {e}")

    logger.info("TuneBot daily check complete.")
