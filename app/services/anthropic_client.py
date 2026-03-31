"""Anthropic Claude API wrapper for content generation."""

import logging
from typing import Optional

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Wrapper around the Anthropic Python SDK for Claude API calls."""

    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is not configured")
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def generate_channel_audit(self, channel_data: dict, videos: list[dict]) -> str:
        """Generate a YouTube channel audit report using Claude.

        Args:
            channel_data: Dict with channel stats (title, subscribers, views, etc.).
            videos: List of recent video dicts with stats.

        Returns:
            Markdown-formatted audit report string.
        """
        client = self._get_client()

        video_summaries = []
        for v in videos[:10]:
            video_summaries.append(
                f"- \"{v.get('title', 'Untitled')}\" "
                f"({v.get('view_count', 0):,} views, "
                f"{v.get('like_count', 0):,} likes, "
                f"{v.get('comment_count', 0):,} comments, "
                f"published {v.get('published_at', 'unknown')})"
            )

        videos_text = "\n".join(video_summaries) if video_summaries else "No recent videos found."

        prompt = f"""You are an expert YouTube growth strategist specialising in music channels. Analyse this channel and provide a detailed, actionable audit report.

## Channel Data
- **Name:** {channel_data.get('title', 'Unknown')}
- **Subscribers:** {channel_data.get('subscriber_count', 0):,}
- **Total Views:** {channel_data.get('view_count', 0):,}
- **Video Count:** {channel_data.get('video_count', 0):,}
- **Created:** {channel_data.get('published_at', 'Unknown')}
- **Description:** {channel_data.get('description', 'None')[:500]}

## Recent Videos (last 10)
{videos_text}

## Instructions
Produce an audit report with these sections:
1. **Channel Overview** - Brief summary of what the channel does and its current standing
2. **Performance Metrics** - Analyse subscriber-to-view ratio, average views per video, engagement rate
3. **Content Strategy** - What's working, what's not, posting frequency analysis
4. **Thumbnail & Title Analysis** - Patterns in the recent video titles
5. **Growth Opportunities** - 5 specific, actionable recommendations
6. **Quick Wins** - 3 things they can do this week

Keep the tone professional but approachable. Use UK English. Format with Markdown headers and bullet points."""

        logger.info(f"Generating channel audit for: {channel_data.get('title', 'Unknown')}")

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        audit_text = message.content[0].text
        logger.info(f"Channel audit generated: {len(audit_text)} characters")
        return audit_text

    async def generate_content(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        model: str = "claude-sonnet-4-20250514",
    ) -> str:
        """General-purpose Claude text generation.

        Args:
            prompt: The user message / prompt.
            system: Optional system message.
            max_tokens: Maximum tokens in response.
            model: Claude model to use.

        Returns:
            Generated text string.
        """
        client = self._get_client()

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = client.messages.create(**kwargs)
        return message.content[0].text

    async def generate_newsletter_section(
        self, topic: str, tracks: list[dict], context: str = ""
    ) -> str:
        """Generate a newsletter section about recent tracks/mixes.

        Args:
            topic: The section topic (e.g. "This Week's Top Tracks").
            tracks: List of track dicts with title, artist, bpm, key info.
            context: Additional context for the newsletter.

        Returns:
            HTML-formatted newsletter section.
        """
        tracks_text = "\n".join(
            f"- {t.get('artist', 'Unknown')} - \"{t.get('title', 'Untitled')}\" "
            f"(BPM: {t.get('bpm', '?')}, Key: {t.get('key', '?')})"
            for t in tracks
        )

        prompt = f"""Write a short, engaging newsletter section for a DJ/music producer audience.

Topic: {topic}
Tracks:
{tracks_text}
{f"Context: {context}" if context else ""}

Requirements:
- Write in a casual, knowledgeable tone
- Keep it under 200 words
- Include practical DJ tips related to the tracks (key compatibility, BPM ranges)
- Output clean HTML suitable for email (use <p>, <strong>, <ul>, <li> tags)
- Use UK English"""

        return await self.generate_content(prompt)


anthropic_client = AnthropicClient()
