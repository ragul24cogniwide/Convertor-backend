import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from app.config import settings
from app.utils.file_utils import delete_job_workspace

logger = logging.getLogger("cleanup")


def cleanup_expired_jobs(ttl_minutes: int = None) -> int:
    """
    Scans the temporary directory and deletes job folders older than ttl_minutes.
    Returns the count of purged job workspaces.
    """
    if ttl_minutes is None:
        ttl_minutes = settings.TEMP_FILE_TTL_MINUTES

    cutoff_time = time.time() - (ttl_minutes * 60)
    purged_count = 0

    if not settings.TEMP_DIR.exists():
        return 0

    for item in settings.TEMP_DIR.iterdir():
        if item.is_dir():
            try:
                # Check modification time of the folder
                mtime = item.stat().st_mtime
                if mtime < cutoff_time:
                    delete_job_workspace(item.name)
                    purged_count += 1
                    logger.info(f"Purged expired job workspace: {item.name}")
            except Exception as e:
                logger.warning(f"Error purging workspace {item.name}: {e}")

    return purged_count


async def periodic_cleanup_task():
    """
    Background worker loop that triggers cleanup at configured intervals.
    """
    logger.info(f"Starting ephemeral file cleanup worker (Interval: {settings.CLEANUP_INTERVAL_MINUTES}m, TTL: {settings.TEMP_FILE_TTL_MINUTES}m)")
    try:
        while True:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_MINUTES * 60)
            try:
                purged = cleanup_expired_jobs()
                if purged > 0:
                    logger.info(f"Cleanup sweep finished. Purged {purged} expired job(s).")
            except Exception as e:
                logger.error(f"Cleanup sweep failed: {e}")
    except asyncio.CancelledError:
        logger.info("Cleanup background worker stopped.")
