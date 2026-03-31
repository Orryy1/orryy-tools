"""Daily cleanup of old temporary files and expired job records."""

import logging
import os
import time
import tempfile
import asyncio

from app.jobs.store import job_store

logger = logging.getLogger(__name__)

# Max age in seconds for temp files (24 hours)
TEMP_MAX_AGE_SECONDS = 86400

# Max age in seconds for completed/failed jobs (7 days)
JOB_MAX_AGE_SECONDS = 7 * 86400

# Directories to scan for orphaned audio temp files
TEMP_DIRS = [tempfile.gettempdir()]

# Extensions to clean up
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


async def run_cleanup() -> None:
    """Daily cleanup cron job.

    1. Removes orphaned audio temp files older than 24 hours.
    2. Purges completed/failed job records older than 7 days from SQLite.
    """
    logger.info("Cleanup job starting...")

    # 1. Clean up temp audio files
    deleted_files = 0
    for temp_dir in TEMP_DIRS:
        deleted_files += await asyncio.to_thread(_clean_temp_dir, temp_dir)

    logger.info(f"Cleanup: removed {deleted_files} orphaned temp files")

    # 2. Purge old job records
    try:
        purged = await job_store.purge_old_jobs(max_age_seconds=JOB_MAX_AGE_SECONDS)
        logger.info(f"Cleanup: purged {purged} old job records")
    except Exception as e:
        logger.error(f"Cleanup: failed to purge old jobs: {e}")

    logger.info("Cleanup job complete.")


def _clean_temp_dir(directory: str) -> int:
    """Remove old audio temp files from a directory. Returns count of deleted files."""
    deleted = 0
    now = time.time()

    try:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue

            try:
                file_age = now - os.path.getmtime(filepath)
                if file_age > TEMP_MAX_AGE_SECONDS:
                    os.unlink(filepath)
                    deleted += 1
            except OSError:
                pass

    except OSError as e:
        logger.warning(f"Cleanup: could not scan {directory}: {e}")

    return deleted
