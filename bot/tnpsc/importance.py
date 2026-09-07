import re
from collections import defaultdict
from datetime import datetime

from ..helper.ext_utils.db_handler import database

STOPWORDS = {"என்ன", "எது", "எந்த", "ஒரு", "மற்றும்", "the", "what", "which", "is", "of", "in", "a"}


async def rebuild_importance():
    if database.db is None:
        return 0
    rows = [row async for row in database.db.tnpsc_pyqs.find({})]
    stats = defaultdict(lambda: {"frequency": 0, "years": set(), "pyq_ids": []})
    for row in rows:
        terms = set(re.findall(r"[\w\u0B80-\u0BFF]{3,}", row.get("question", "").lower())) - STOPWORDS
        for term in terms:
            stats[term]["frequency"] += 1
            if row.get("year"):
                stats[term]["years"].add(row["year"])
            stats[term]["pyq_ids"].append(row["_id"])
    for term, value in stats.items():
        await database.db.tnpsc_importance.update_one(
            {"_id": term},
            {"$set": {"topic": term, "frequency": value["frequency"], "distinct_years": len(value["years"]), "score": value["frequency"] + len(value["years"]) * 2, "pyq_ids": value["pyq_ids"], "updated_at": datetime.utcnow()}},
            upsert=True,
        )
    return len(stats)


async def top_topics(limit=10):
    if database.db is None:
        return []
    cursor = database.db.tnpsc_importance.find({}).sort("score", -1).limit(limit)
    return [item async for item in cursor]

