from html import escape
from time import time
from urllib.parse import quote

from file_stream_utils import create_file_token

from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.telegram_helper.message_utils import send_message


@new_task
async def file_link(_, message):
    reply = message.reply_to_message
    media = None
    if reply:
        for key in ("document", "video", "audio", "animation", "voice"):
            media = getattr(reply, key, None)
            if media:
                break
    if not reply or not media:
        await send_message(message, "Reply to a Telegram file with <code>/link</code>.")
        return
    base_url = (Config.BASE_URL or "").rstrip("/")
    if not base_url:
        await send_message(message, "<code>BASE_URL</code> is not configured.")
        return
    token = create_file_token(
        reply.chat.id, reply.id, int(time()) + 3600,
        Config.BOT_TOKEN, Config.WEB_ACCESS_PASSWORD,
    )
    name = getattr(media, "file_name", None) or f"telegram-{reply.id}"
    url = f"{base_url}/dl/{token}/{quote(name, safe='')}"
    await send_message(
        message,
        f"<b>Download link (valid for 1 hour):</b>\n<a href=\"{escape(url)}\">{escape(name)}</a>",
    )
