from datetime import date, datetime

from pyrogram.filters import command, user
from pyrogram.handlers import MessageHandler

from .. import LOGGER
from ..core.config_manager import Config
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.message_utils import send_message
from .jobs.repository import jobs
from .syllabus import build_daily_plan, get_progress
from .ai import get_provider
from .ai.base import AIRequest
from .retrieval import format_context, retrieve
from .pyq import search_pyqs
from .importance import top_topics
from .student import complete_minutes, quiz_items, revision_items


def _owner_id():
    try:
        return int(getattr(Config, "TNPSC_OWNER_USER_ID", 0) or Config.OWNER_ID or 0)
    except (TypeError, ValueError):
        return 0


def _exam_date():
    try:
        return date.fromisoformat(getattr(Config, "TNPSC_EXAM_DATE", "2026-12-20"))
    except ValueError:
        return date(2026, 12, 20)


def _owner_filter():
    owner = _owner_id()
    return user(owner) if owner else user(0)


async def _save_progress(user_id, **values):
    if database.db is None:
        return
    collection = database.db.tnpsc_progress
    await collection.update_one(
        {"_id": f"{database._partition()}:{user_id}"},
        {"$set": {**values, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


async def countdown(_, message):
    remaining = max(0, (_exam_date() - date.today()).days)
    await send_message(
        message,
        f"⏳ <b>TNPSC Group 4 Countdown</b>\n\n"
        f"Exam date: <b>{_exam_date().isoformat()}</b>\n"
        f"Days remaining: <b>{remaining}</b>\n\n"
        "Stay consistent. Today’s completed study is more important than tomorrow’s plan.",
    )


async def today(_, message):
    user_id = message.from_user.id
    await _save_progress(user_id, last_seen_date=date.today().isoformat())
    tasks = await build_daily_plan(user_id)
    remaining = max(0, (_exam_date() - date.today()).days)
    await send_message(
        message,
        "📅 <b>Today’s TNPSC Coach Plan</b>\n\n"
        + "\n".join(f"{i}. {task['title']} ({task['minutes']} min)" for i, task in enumerate(tasks, 1))
        + "\n5. 📚 Learn today’s English word: <b>Consistency</b> — <b>தொடர்ச்சியான முயற்சி</b>\n\n"
        f"⏳ {remaining} days remain. Mark each task complete before resting.",
    )


async def progress(_, message):
    data = await get_progress(message.from_user.id)
    await send_message(message, f"📊 <b>Your Progress</b>\n\nCompleted minutes: <b>{data.get('completed_minutes', 0)}</b>\nLast activity: <b>{data.get('last_seen_date', 'Not started')}</b>")


async def enqueue_daily_plan(_, message):
    job_id = await jobs.enqueue("GENERATE_DAILY_TIMETABLE", {"user_id": message.from_user.id}, f"daily-plan:{message.from_user.id}:{date.today().isoformat()}")
    await send_message(message, f"✅ Daily timetable job queued.\nJob: <code>{job_id or 'database unavailable'}</code>")


async def ask(_, message):
    question = (message.text or "").split(maxsplit=1)
    if len(question) < 2:
        await send_message(message, "Usage: <code>/ask உங்கள் TNPSC கேள்வி</code>")
        return
    items = await retrieve(question[1])
    if not items:
        await send_message(message, "📚 இந்த கேள்விக்கான சேமிக்கப்பட்ட பாடநூல் ஆதாரம் கிடைக்கவில்லை. தயவுசெய்து முதலில் அந்தப் பொருளை source channel-ல் சேர்க்கவும்.")
        return
    context = format_context(items)
    request = AIRequest(
        system="You are a careful Tamil TNPSC Group 4 tutor. Answer only from the supplied source context. If the context is insufficient, say so. Never invent textbook facts. Reply mainly in Tamil and include the source numbers.",
        prompt=f"Question: {question[1]}\n\nSource context:\n{context}",
        max_tokens=600,
    )
    try:
        answer = await get_provider().generate(request)
    except Exception as error:
        LOGGER.warning("TNPSC tutor provider failed: %s", type(error).__name__)
        await send_message(message, "⚠️ AI tutor is temporarily unavailable. Please try again later.")
        return
    await send_message(message, f"🧠 <b>TNPSC Tutor</b>\n\n{answer}\n\n<i>Answer generated from stored textbook sources.</i>")


async def pyq(_, message):
    parts = (message.text or "").split(maxsplit=1)
    results = await search_pyqs(parts[1] if len(parts) > 1 else "")
    if not results:
        await send_message(message, "📝 No stored PYQs found yet. Upload a question paper to the configured source channel.")
        return
    body = "\n\n".join(f"{index}. {item['question']}" for index, item in enumerate(results, 1))
    await send_message(message, f"📝 <b>Previous Questions</b>\n\n{body}")


async def important(_, message):
    topics = await top_topics()
    if not topics:
        await send_message(message, "🎯 Importance data is not available yet. Upload PYQs first.")
        return
    body = "\n".join(f"{index}. <b>{item['topic']}</b> — {item['frequency']} PYQs, {item['distinct_years']} years, score {item['score']}" for index, item in enumerate(topics, 1))
    await send_message(message, f"🎯 <b>Important PYQ Topics</b>\n\n{body}\n\n<i>Based only on stored PYQ data.</i>")


async def complete(_, message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await send_message(message, "Usage: <code>/complete 60</code>")
        return
    total = await complete_minutes(message.from_user.id, int(parts[1]))
    await send_message(message, f"✅ Study session recorded. Total completed: <b>{total} minutes</b>")


async def revision(_, message):
    topics = await revision_items()
    if not topics:
        await send_message(message, "🔄 Revision items will appear after PYQ data is imported.")
        return
    body = "\n".join(f"• {item['topic']} — revise from {item['frequency']} PYQs" for item in topics)
    await send_message(message, f"🔄 <b>Revision Priority</b>\n\n{body}")


async def quiz(_, message):
    parts = (message.text or "").split(maxsplit=1)
    items = await quiz_items(parts[1] if len(parts) > 1 else "")
    if not items:
        await send_message(message, "🤖 No source-backed quiz questions are available yet. Import PYQs first.")
        return
    body = "\n\n".join(f"{index}. {item['question']}" for index, item in enumerate(items, 1))
    await send_message(message, f"🤖 <b>Source-backed Quiz</b>\n\n{body}\n\nReply with your answers in order. Answers will be added after the structured PYQ importer is expanded.")


async def word(_, message):
    await send_message(
        message,
        "📖 <b>Today’s English Word</b>\n\n"
        "<b>Consistency</b>\n"
        "தமிழ்: <b>தொடர்ச்சியான முயற்சி</b>\n"
        "Meaning: தொடர்ந்து செய்வது வெற்றிக்கு வழிவகுக்கும்.\n"
        "Example: Consistency is more powerful than occasional hard work.",
    )


async def motivation(_, message):
    await send_message(
        message,
        "🔥 <b>Today’s Motivation</b>\n\n"
        "ஒரே நாளில் பெரிய மாற்றம் வராது. ஆனால் ஒவ்வொரு நாளும் செய்யும் சிறிய முயற்சிகள், தேர்வு நாளில் பெரிய வெற்றியாக மாறும்.\n\n"
        "இன்று திட்டத்தை முடி. நாளைய நம்பிக்கையை இன்று உருவாக்கு.",
    )


def register_handlers(client):
    owner = _owner_filter()
    client.add_handler(MessageHandler(countdown, command("countdown") & owner))
    client.add_handler(MessageHandler(today, command(["today", "timetable"]) & owner))
    client.add_handler(MessageHandler(word, command("word") & owner))
    client.add_handler(MessageHandler(motivation, command("motivation") & owner))
    client.add_handler(MessageHandler(progress, command("progress") & owner))
    client.add_handler(MessageHandler(enqueue_daily_plan, command("refreshplan") & owner))
    client.add_handler(MessageHandler(ask, command("ask") & owner))
    client.add_handler(MessageHandler(pyq, command("pyq") & owner))
    client.add_handler(MessageHandler(important, command("important") & owner))
    client.add_handler(MessageHandler(complete, command("complete") & owner))
    client.add_handler(MessageHandler(revision, command("revision") & owner))
    client.add_handler(MessageHandler(quiz, command("quiz") & owner))
    LOGGER.info("TNPSC private study coach handlers registered")
