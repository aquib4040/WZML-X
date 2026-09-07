import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from ... import LOGGER, bot_loop
from .repository import jobs


async def _worker():
    worker_id = str(uuid4())
    while True:
        job = await jobs.claim(worker_id)
        if not job:
            await asyncio.sleep(5)
            continue
        try:
            if job.get("job_type") == "GENERATE_DAILY_TIMETABLE":
                from ..syllabus import build_daily_plan

                await build_daily_plan(job.get("payload", {}).get("user_id"))
            elif job.get("job_type") == "IMPORT_DOCUMENT":
                # Extraction and AI analysis are implemented in Phase 5.
                await jobs.finish(job["_id"], "deferred", "Document extraction scheduled for Phase 5")
                continue
            await jobs.finish(job["_id"])
        except Exception as error:
            attempts = job.get("attempts", 1)
            if attempts < job.get("max_attempts", 3):
                if jobs.collection is not None:
                    await jobs.collection.update_one(
                        {"_id": job["_id"]},
                        {"$set": {"status": "retrying", "available_at": datetime.utcnow() + timedelta(seconds=min(300, 2**attempts * 5)), "error": str(error), "updated_at": datetime.utcnow()}},
                    )
            else:
                await jobs.finish(job["_id"], "failed", str(error))
            LOGGER.exception("TNPSC job failed: %s", job.get("_id"))


def start_worker():
    return bot_loop.create_task(_worker())
