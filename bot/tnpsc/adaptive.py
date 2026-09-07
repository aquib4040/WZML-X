from datetime import date, datetime, timedelta

from ..helper.ext_utils.db_handler import database
from .importance import top_topics


OFFICIAL_GROUP4_SYLLABUS = {
    "Tamil Eligibility-cum-Scoring Test": 100,
    "General Studies": 75,
    "Aptitude and Mental Ability": 25,
}


async def adapt_plan(user_id):
    if database.db is None:
        return []
    progress = await database.db.tnpsc_progress.find_one({"_id": f"{database._partition()}:{user_id}"}) or {}
    weak = progress.get("weak_topics", [])
    important = await top_topics(5)
    topics = weak or [item["topic"] for item in important]
    if not topics:
        topics = ["Tamil Eligibility-cum-Scoring", "General Studies", "Aptitude and Mental Ability"]
    tasks = [
        {"kind": "WEAK_TOPIC", "title": f"Revise weak topic: {topic}", "minutes": 60, "completed": False}
        for topic in topics[:3]
    ]
    tasks.extend([
        {"kind": "PYQ", "title": "Solve 25 timed PYQs", "minutes": 60, "completed": False},
        {"kind": "ERROR_REVIEW", "title": "Review wrong answers", "minutes": 30, "completed": False},
    ])
    today = date.today().isoformat()
    await database.db.tnpsc_daily_tasks.replace_one(
        {"_id": f"{database._partition()}:{user_id}:{today}"},
        {"_id": f"{database._partition()}:{user_id}:{today}", "user_id": user_id, "date": today, "mode": "adaptive", "tasks": tasks, "updated_at": datetime.utcnow()},
        upsert=True,
    )
    return tasks


async def create_mock(user_id, limit=20):
    if database.db is None:
        return None
    rows = [row async for row in database.db.tnpsc_pyqs.find({}).limit(limit)]
    mock_id = f"{database._partition()}:{user_id}:{datetime.utcnow().timestamp()}"
    await database.db.tnpsc_quizzes.insert_one({"_id": mock_id, "user_id": user_id, "kind": "mock", "question_ids": [row["_id"] for row in rows], "question_count": len(rows), "created_at": datetime.utcnow(), "status": "started"})
    return mock_id, len(rows)

