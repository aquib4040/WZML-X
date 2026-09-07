import asyncio
import re
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
                await _import_document(job)
            elif job.get("job_type") == "REBUILD_IMPORTANCE":
                from ..importance import rebuild_importance

                await rebuild_importance()
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


async def _import_document(job):
    from datetime import datetime

    from ..extraction.document import chunks, extract
    from ...helper.ext_utils.db_handler import database

    source_id = job.get("payload", {}).get("source_id")
    source = await database.db.tnpsc_sources.find_one({"_id": source_id})
    if not source or not source.get("local_path"):
        raise ValueError("source file is unavailable")
    pages = extract(source["local_path"])
    if source.get("source_type") == "pyq":
        from ..pyq import save_pyq

        for page in pages:
            for question in re.split(r"\n+|(?<=\?) ", page["text"]):
                if "?" in question:
                    await save_pyq(question, source_id=source_id)
        await database.db.tnpsc_sources.update_one(
            {"_id": source_id},
            {"$set": {"processing_status": "pyq_imported", "page_count": len(pages), "updated_at": datetime.utcnow()}},
        )
        return
    records = database.db.tnpsc_knowledge
    for item in chunks(pages):
        knowledge_id = f"{source_id}:{item['content_hash']}"
        await records.update_one(
            {"_id": knowledge_id},
            {"$setOnInsert": {"_id": knowledge_id, "source_id": source_id, "language": "ta", "kind": "source_chunk", "content": {"statement": item["text"]}, "source_reference": {"page": item["page"], "telegram_message_id": source["source_reference"].get("telegram_message_id")}, "verification": {"status": "source-backed", "ai_generated": False}, "content_hash": item["content_hash"], "created_at": datetime.utcnow()}},
            upsert=True,
        )
    await database.db.tnpsc_sources.update_one({"_id": source_id}, {"$set": {"processing_status": "extracted", "page_count": len(pages), "updated_at": datetime.utcnow()}})


def start_worker():
    return bot_loop.create_task(_worker())
