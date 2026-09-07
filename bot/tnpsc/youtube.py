import re
from urllib.parse import urlparse

from ..helper.ext_utils.db_handler import database
from .jobs.repository import jobs


def valid_youtube_url(url):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


async def enqueue_summary(user_id, url):
    if not valid_youtube_url(url):
        raise ValueError("Only YouTube URLs are supported")
    return await jobs.enqueue("SUMMARIZE_YOUTUBE", {"user_id": user_id, "url": url}, f"youtube:{url}")

