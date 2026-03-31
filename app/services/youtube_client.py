"""YouTube Data API v3 wrapper for channel stats and recent videos."""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeClient:
    """Wrapper around YouTube Data API v3."""

    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY

    def _check_key(self) -> None:
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY is not configured")

    async def get_channel_by_id(self, channel_id: str) -> dict:
        """Fetch channel details by channel ID.

        Args:
            channel_id: YouTube channel ID (e.g. UCxxxxx).

        Returns:
            Dict with channel snippet, statistics, and brandingSettings.
        """
        self._check_key()
        params = {
            "part": "snippet,statistics,brandingSettings,contentDetails",
            "id": channel_id,
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{YOUTUBE_API_BASE}/channels", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if not items:
            raise ValueError(f"Channel not found: {channel_id}")

        channel = items[0]
        snippet = channel.get("snippet", {})
        stats = channel.get("statistics", {})

        return {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "custom_url": snippet.get("customUrl", ""),
            "published_at": snippet.get("publishedAt", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "uploads_playlist_id": (
                channel.get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads", "")
            ),
        }

    async def get_channel_by_handle(self, handle: str) -> dict:
        """Fetch channel details by handle (@username).

        Args:
            handle: YouTube handle (with or without @).

        Returns:
            Dict with channel details.
        """
        self._check_key()
        if not handle.startswith("@"):
            handle = f"@{handle}"

        params = {
            "part": "snippet,statistics,contentDetails",
            "forHandle": handle,
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{YOUTUBE_API_BASE}/channels", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if not items:
            raise ValueError(f"Channel not found for handle: {handle}")

        channel_id = items[0]["id"]
        return await self.get_channel_by_id(channel_id)

    async def get_recent_videos(
        self, uploads_playlist_id: str, max_results: int = 10
    ) -> list[dict]:
        """Fetch recent videos from a channel's uploads playlist.

        Args:
            uploads_playlist_id: The uploads playlist ID from channel details.
            max_results: Maximum number of videos to return (1-50).

        Returns:
            List of dicts with video details.
        """
        self._check_key()
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(max_results, 50),
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{YOUTUBE_API_BASE}/playlistItems", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        video_ids = [
            item["contentDetails"]["videoId"]
            for item in items
            if item.get("contentDetails", {}).get("videoId")
        ]

        if not video_ids:
            return []

        # Fetch video statistics in bulk
        stats_params = {
            "part": "statistics,contentDetails,snippet",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            stats_resp = await client.get(f"{YOUTUBE_API_BASE}/videos", params=stats_params)
            stats_resp.raise_for_status()
            stats_data = stats_resp.json()

        videos = []
        for item in stats_data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            videos.append({
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "description": snippet.get("description", "")[:500],
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "duration": content.get("duration", ""),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            })

        return videos

    async def search_channels(self, query: str, max_results: int = 5) -> list[dict]:
        """Search for YouTube channels by query.

        Args:
            query: Search query string.
            max_results: Maximum results to return.

        Returns:
            List of dicts with channel_id and title.
        """
        self._check_key()
        params = {
            "part": "snippet",
            "type": "channel",
            "q": query,
            "maxResults": min(max_results, 25),
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{YOUTUBE_API_BASE}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            results.append({
                "channel_id": item.get("id", {}).get("channelId", ""),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:300],
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            })
        return results


youtube_client = YouTubeClient()
