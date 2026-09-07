import hashlib
import re
from datetime import datetime

from ..helper.ext_utils.db_handler import database


def normalize_question(text):
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


async def save_pyq(question, source_id=None, year=None, exam="TNPSC Group 4"):
    normalized = normalize_question(question)
    if not normalized or database.db is None:
        return None
    pyq_id = hashlib.sha256(normalized.encode()).hexdigest()
    await database.db.tnpsc_pyqs.update_one(
        {"_id": pyq_id},
        {"$setOnInsert": {"_id": pyq_id, "question": question.strip(), "exam": exam, "year": year, "source_id": source_id, "mapping_status": "pending", "created_at": datetime.utcnow()}},
        upsert=True,
    )
    return pyq_id


async def search_pyqs(query, limit=10):
    if database.db is None:
        return []
    terms = [term for term in normalize_question(query).split() if len(term) > 2][:6]
    if not terms:
        return []
    cursor = database.db.tnpsc_pyqs.find({"$or": [{"question": {"$regex": re.escape(term), "$options": "i"}} for term in terms]}).limit(limit)
    return [item async for item in cursor]

