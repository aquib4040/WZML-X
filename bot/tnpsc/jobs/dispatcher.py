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
            elif job.get("job_type") == "SUMMARIZE_YOUTUBE":
                await _summarize_youtube(job)
            elif job.get("job_type") == "SCOUT_OFFICIAL_SOURCES":
                from ..scout import scout_official_sources

                await scout_official_sources()
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


async def _summarize_youtube(job):
    from asyncio import to_thread
    from yt_dlp import YoutubeDL
    from ..ai import get_provider
    from ..ai.base import AIRequest
    from ... import user_data
    from ...core.config_manager import Config

    url = job.get("payload", {}).get("url")
    options = {"quiet": True, "skip_download": True, "noplaylist": True}
    user_id = job.get("payload", {}).get("user_id")
    user_settings = user_data.get(user_id, {})
    cookies = user_settings.get("USER_COOKIE_FILE") or getattr(Config, "YOUTUBE_COOKIES_FILE", "")
    if cookies:
        options["cookiefile"] = cookies

    def metadata():
        with YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)

    info = await to_thread(metadata)
    title = info.get("title", "YouTube study video")
    description = info.get("description", "")[:12000]
    prompt = f"Title: {title}\nDescription/transcript if available:\n{description}\n\nCreate a concise Tamil TNPSC study summary, important points, and five source-limited MCQs. If evidence is insufficient, say so."
    result = await get_provider().generate(AIRequest(system="You are a careful Tamil TNPSC tutor. Never invent facts.", prompt=prompt, max_tokens=1000))
    if database.db is not None:
        await database.db.tnpsc_sources.update_one({"source_reference.url": url}, {"$set": {"title": title, "summary": result, "processing_status": "complete", "metadata": {"video_id": info.get("id"), "duration": info.get("duration"), "token_pickle_available": bool(user_settings.get("TOKEN_PICKLE")), "gdrive_id": user_settings.get("GDRIVE_ID")}, "updated_at": datetime.utcnow()}}, upsert=True)


def start_worker():
    return bot_loop.create_task(_worker())
