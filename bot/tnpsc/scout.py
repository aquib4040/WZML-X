from datetime import datetime
from hashlib import sha256

from httpx import AsyncClient

from ..helper.ext_utils.db_handler import database

OFFICIAL_SOURCES = (
    "https://tnpsc.gov.in/",
    "https://tnpsc.gov.in/static_pdf/syllabus/G4_Scheme_Revised_27012022.pdf",
    "https://textbookcorp.in/",
    "https://textbookcorp.in/textbook/schools/books",
    "https://www.tn.gov.in/",
)


async def scout_official_sources():
    if database.db is None:
        return 0
    count = 0
    async with AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in OFFICIAL_SOURCES:
            try:
                response = await client.get(url)
                response.raise_for_status()
                digest = sha256(response.content).hexdigest()
                await database.db.tnpsc_sources.update_one(
                    {"source_reference.url": url, "content_hash": digest},
                    {"$set": {"source_type": "official_web", "title": url, "authorized": True, "source_reference": {"url": url}, "processing_status": "discovered", "content_preview": response.text[:4000], "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
                count += 1
            except Exception:
                continue
    return count
