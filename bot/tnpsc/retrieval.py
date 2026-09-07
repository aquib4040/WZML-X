import re

from ..helper.ext_utils.db_handler import database


def _terms(text):
    return {term for term in re.findall(r"[\w\u0B80-\u0BFF]{2,}", text.lower())}


async def retrieve(query, limit=5):
    if database.db is None:
        return []
    terms = list(_terms(query))
    if not terms:
        return []
    clauses = [{"content.statement": {"$regex": re.escape(term), "$options": "i"}} for term in terms[:8]]
    cursor = database.db.tnpsc_knowledge.find({"$or": clauses}).limit(limit)
    return [item async for item in cursor]


def format_context(items):
    return "\n\n".join(
        f"[{index}] {item.get('content', {}).get('statement', '')} "
        f"(Class {item.get('class_level', '?')}, {item.get('subject', '?')}, chapter {item.get('chapter_id', '?')})"
        for index, item in enumerate(items, 1)
    )

