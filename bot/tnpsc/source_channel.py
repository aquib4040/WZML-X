import hashlib
from pathlib import Path
from datetime import datetime

from pyrogram.filters import channel
from pyrogram.handlers import MessageHandler

from .. import DOWNLOAD_DIR, LOGGER, bot_loop
from ..core.config_manager import Config
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.message_utils import send_message
from .jobs.repository import jobs


def _channel_id():
    try:
        return int(Config.TNPSC_SOURCE_CHANNEL_ID or 0)
    except (TypeError, ValueError):
        return 0


def _source_type(message):
    if message.document:
        return "document"
    if message.photo:
        return "image"
    if message.text:
        return "text"
    return None


def _file_id(message):
    media = message.document or message.photo
    return getattr(media, "file_id", None)


def _content_hash(message):
    value = message.text or _file_id(message) or f"{message.chat.id}:{message.id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _ingest(client, message):
    if database.db is None:
        LOGGER.warning("TNPSC source message ignored because MongoDB is unavailable")
        return
    kind = _source_type(message)
    if not kind:
        return
    source_key = f"{message.chat.id}:{message.id}"
    sources = database.db.tnpsc_sources
    if await sources.find_one({"_id": source_key}):
        return
    now = datetime.utcnow()
    source = {
        "_id": source_key,
        "source_type": kind,
        "language": "ta",
        "content_hash": _content_hash(message),
        "source_reference": {"telegram_chat_id": message.chat.id, "telegram_message_id": message.id},
        "telegram_file_id": _file_id(message),
        "caption": message.caption or "",
        "text": message.text or "",
        "processing_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    if message.document or message.photo:
        target_dir = Path(DOWNLOAD_DIR) / "tnpsc_sources"
        target_dir.mkdir(parents=True, exist_ok=True)
        source["local_path"] = await message.download(file_name=str(target_dir / source_key.replace(":", "_")))
    duplicate = await sources.find_one({"content_hash": source["content_hash"]})
    if duplicate:
        source["processing_status"] = "duplicate"
        source["duplicate_of"] = duplicate["_id"]
    await sources.insert_one(source)
    if source["processing_status"] == "duplicate":
        return
    job_id = await jobs.enqueue("IMPORT_DOCUMENT", {"source_id": source_key}, f"import-source:{source_key}")
    await sources.update_one({"_id": source_key}, {"$set": {"job_id": job_id, "processing_status": "queued"}})


async def source_message(client, message):
    try:
        await _ingest(client, message)
    except Exception:
        LOGGER.exception("TNPSC source-channel ingestion failed for message %s", message.id)


def register_source_handler(client):
    source_id = _channel_id()
    if not source_id or not Config.TNPSC_SOURCE_CHANNEL_ENABLED:
        LOGGER.info("TNPSC source-channel ingestion is disabled")
        return
    client.add_handler(MessageHandler(source_message, channel(source_id)))
    LOGGER.info("TNPSC source-channel handler registered for configured channel")
