from datetime import date

from ..helper.ext_utils.db_handler import database
from .. import user_data


DEFAULT_TASKS = (
    ("TEXTBOOK", "Study one Tamil-medium textbook topic", 90),
    ("PYQ", "Solve 20 previous-year questions", 60),
    ("ERROR_REVIEW", "Review every wrong answer", 30),
    ("REVISION", "Revise yesterday’s topic", 30),
)


async def get_progress(user_id):
    if database.db is None:
        return {}
    return await database.db.tnpsc_progress.find_one({"_id": f"{database._partition()}:{user_id}"}) or {}


async def save_daily_plan(user_id, tasks):
    if database.db is None:
        return
    today = date.today().isoformat()
    await database.db.tnpsc_daily_tasks.replace_one(
        {"_id": f"{database._partition()}:{user_id}:{today}"},
        {"_id": f"{database._partition()}:{user_id}:{today}", "user_id": user_id, "date": today, "tasks": tasks, "updated_at": date.today().isoformat()},
        upsert=True,
    )


async def build_daily_plan(user_id):
    progress = await get_progress(user_id)
    completed = progress.get("completed_minutes", 0)
    preferences = user_data.get(user_id, {})
    start = preferences.get("TNPSC_STUDY_START", "06:30")
    slots = ["06:30-08:00", "10:00-11:00", "18:00-18:30", "20:00-20:30"]
    if start != "06:30":
        slots = [f"{start} onward", "Midday", "Evening", "Night"]
    tasks = [{"kind": kind, "title": title, "minutes": minutes, "time": slots[index], "completed": False} for index, (kind, title, minutes) in enumerate(DEFAULT_TASKS)]
    if completed >= 180:
        tasks[0]["minutes"] = 60
        tasks[1]["minutes"] = 45
    await save_daily_plan(user_id, tasks)
    return tasks
