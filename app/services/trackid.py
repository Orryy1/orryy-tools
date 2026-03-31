"""Track identification service using AcoustID / Chromaprint."""

import logging
import tempfile
import os
import asyncio
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ACOUSTID_LOOKUP_URL = "https://api.acoustid.org/v2/lookup"


async def identify_track(file_bytes: bytes, filename: str = "unknown") -> dict:
    """Identify a track using AcoustID fingerprinting.

    Generates a Chromaprint fingerprint of the audio file, then looks it up
    against the AcoustID database to find matching recordings.

    Args:
        file_bytes: Raw audio file bytes.
        filename: Original filename for logging.

    Returns:
        Dict with identification results.
    """
    logger.info(f"Identifying track: {filename} ({len(file_bytes)} bytes)")

    suffix = os.path.splitext(filename)[1] if "." in filename else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # Use pyacoustid to generate fingerprint
        # This requires the chromaprint/fpcalc binary to be installed
        import acoustid

        duration, fingerprint = await asyncio.to_thread(
            acoustid.fingerprint_file, tmp_path
        )

        logger.info(f"Generated fingerprint for {filename} (duration: {duration}s)")

        # Look up the fingerprint against AcoustID
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                ACOUSTID_LOOKUP_URL,
                data={
                    "client": settings.ACOUSTID_API_KEY,
                    "duration": str(int(duration)),
                    "fingerprint": fingerprint,
                    "meta": "recordings releasegroups",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            logger.info(f"No AcoustID match found for {filename}")
            return {
                "identified": False,
                "title": None,
                "artist": None,
                "album": None,
                "release_date": None,
                "score": None,
                "acoustid": None,
                "recordings": [],
            }

        # Take the best match
        best = results[0]
        score = best.get("score", 0)
        acoustid_id = best.get("id")
        recordings = best.get("recordings", [])

        title = None
        artist = None
        album = None
        release_date = None

        if recordings:
            rec = recordings[0]
            title = rec.get("title")
            artists = rec.get("artists", [])
            if artists:
                artist = artists[0].get("name")

            release_groups = rec.get("releasegroups", [])
            if release_groups:
                rg = release_groups[0]
                album = rg.get("title")
                release_date = rg.get("firstreleasedate")

        result = {
            "identified": True,
            "title": title,
            "artist": artist,
            "album": album,
            "release_date": release_date,
            "score": round(score, 4),
            "acoustid": acoustid_id,
            "recordings": recordings[:5],  # Limit to top 5
        }
        logger.info(f"Identified {filename}: {artist} - {title} (score: {score})")
        return result

    except Exception as e:
        logger.error(f"Track identification failed for {filename}: {e}", exc_info=True)
        raise

    finally:
        os.unlink(tmp_path)
