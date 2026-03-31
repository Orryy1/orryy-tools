"""Stem separation service using Replicate API (demucs model)."""

import logging
import asyncio
import replicate

from app.config import settings
from app.services.storage import upload_file_to_r2, generate_presigned_url

logger = logging.getLogger(__name__)

DEMUCS_MODEL = "cjwbw/demucs:25a173108cff36ef9f80f854c162d01df9e6528be175794b81571f6c6c7b56f9"


async def run_stem_separation(
    file_bytes: bytes,
    filename: str,
    job_id: str,
    jobs_store: dict,
) -> dict:
    """Run stem separation via Replicate and upload results to R2.

    Updates the jobs_store in-place as processing progresses.

    Args:
        file_bytes: Raw audio file bytes.
        filename: Original filename.
        job_id: The job ID to track progress.
        jobs_store: Reference to the in-memory jobs dict.

    Returns:
        Dict with download URLs for each stem.
    """
    try:
        jobs_store[job_id].status = "processing"
        jobs_store[job_id].progress = 0.1
        logger.info(f"Starting stem separation for job {job_id}: {filename}")

        # Upload input file to R2 for Replicate to access
        input_key = f"stems/input/{job_id}/{filename}"
        await upload_file_to_r2(file_bytes, input_key, content_type="audio/mpeg")
        input_url = await generate_presigned_url(input_key, expires_in=3600)

        jobs_store[job_id].progress = 0.2

        # Run demucs on Replicate
        output = await asyncio.to_thread(
            replicate.run,
            DEMUCS_MODEL,
            input={"audio": input_url},
        )

        jobs_store[job_id].progress = 0.7
        logger.info(f"Replicate returned output for job {job_id}")

        # output is typically a dict with stem URLs from Replicate
        # Download each stem and re-upload to our R2 for persistent storage
        import httpx

        stem_names = ["vocals", "drums", "bass", "other"]
        result_urls = {}

        async with httpx.AsyncClient(timeout=120.0) as client:
            for stem_name in stem_names:
                stem_url = output.get(stem_name)
                if not stem_url:
                    logger.warning(f"No {stem_name} stem in Replicate output for job {job_id}")
                    continue

                # Download from Replicate's temporary URL
                resp = await client.get(str(stem_url))
                resp.raise_for_status()
                stem_bytes = resp.content

                # Upload to R2
                r2_key = f"stems/output/{job_id}/{stem_name}.wav"
                await upload_file_to_r2(stem_bytes, r2_key, content_type="audio/wav")

                # Generate presigned download URL (valid 24h)
                download_url = await generate_presigned_url(r2_key, expires_in=86400)
                result_urls[stem_name] = download_url

                logger.info(f"Uploaded {stem_name} stem for job {job_id} ({len(stem_bytes)} bytes)")

        jobs_store[job_id].progress = 1.0
        jobs_store[job_id].status = "complete"
        jobs_store[job_id].result = result_urls
        logger.info(f"Stem separation complete for job {job_id}")
        return result_urls

    except Exception as e:
        logger.error(f"Stem separation failed for job {job_id}: {e}", exc_info=True)
        jobs_store[job_id].status = "failed"
        jobs_store[job_id].error = str(e)
        raise
