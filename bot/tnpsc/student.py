from datetime import date, datetime

from ..helper.ext_utils.db_handler import database
from .importance import top_topics
from .pyq import search_pyqs


async def complete_minutes(user_id, minutes):
    if database.db is None:
        return 0
    key = f"{database._partition()}:{user_id}"
    current = await database.db.tnpsc_progress.find_one({"_id": key}) or {}
    total = int(current.get("completed_minutes", 0)) + max(0, int(minutes))
    await database.db.tnpsc_progress.update_one({"_id": key}, {"$set": {"completed_minutes": total, "last_seen_date": date.today().isoformat(), "updated_at": datetime.utcnow()}, "$inc": {"study_sessions": 1}}, upsert=True)
    return total


async def revision_items(limit=10):
    return await top_topics(limit)


async def quiz_items(query="", limit=5):
    return await search_pyqs(query, limit)

