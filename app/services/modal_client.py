"""Wrapper for calling Modal serverless functions."""

import logging
import asyncio
from typing import Any, Optional

import modal

from app.config import settings

logger = logging.getLogger(__name__)


class ModalClient:
    """Client for invoking Modal functions remotely."""

    def __init__(self):
        self._initialized = False

    def _ensure_env(self) -> None:
        """Set Modal environment variables if configured."""
        if not self._initialized:
            import os
            if settings.MODAL_TOKEN_ID:
                os.environ.setdefault("MODAL_TOKEN_ID", settings.MODAL_TOKEN_ID)
            if settings.MODAL_TOKEN_SECRET:
                os.environ.setdefault("MODAL_TOKEN_SECRET", settings.MODAL_TOKEN_SECRET)
            self._initialized = True

    async def call_mashup(
        self,
        track_a_url: str,
        track_b_url: str,
        target_bpm: float,
        target_key: str,
        preview_duration: float = 30.0,
    ) -> bytes:
        """Call the Modal mashup function to generate a mashup preview.

        Args:
            track_a_url: Presigned URL for track A.
            track_b_url: Presigned URL for track B.
            target_bpm: Target BPM for alignment.
            target_key: Target musical key.
            preview_duration: Length of preview in seconds.

        Returns:
            WAV bytes of the mashup preview.
        """
        self._ensure_env()
        logger.info(f"Calling Modal mashup: bpm={target_bpm}, key={target_key}, dur={preview_duration}s")

        fn = modal.Function.from_name("orryy-mashup", "generate_mashup_preview")
        result = await asyncio.to_thread(
            fn.remote,
            track_a_url=track_a_url,
            track_b_url=track_b_url,
            target_bpm=target_bpm,
            target_key=target_key,
            preview_duration=preview_duration,
        )
        logger.info(f"Modal mashup returned {len(result)} bytes")
        return result

    async def call_trackid(self, audio_url: str) -> dict:
        """Call the Modal track identification function.

        Args:
            audio_url: Presigned URL to the audio file.

        Returns:
            Dict with identification results.
        """
        self._ensure_env()
        logger.info(f"Calling Modal trackid for URL: {audio_url[:80]}...")

        fn = modal.Function.from_name("orryy-trackid", "identify_track_remote")
        result = await asyncio.to_thread(
            fn.remote,
            audio_url=audio_url,
            acoustid_api_key=settings.ACOUSTID_API_KEY,
        )
        logger.info(f"Modal trackid result: identified={result.get('identified')}")
        return result


modal_client = ModalClient()
