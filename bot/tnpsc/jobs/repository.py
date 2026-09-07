from datetime import datetime, timedelta
from uuid import uuid4

from ...helper.ext_utils.db_handler import database


class JobRepository:
    def __init__(self):
        self.collection_name = "tnpsc_ai_jobs"

    @property
    def collection(self):
        return database.db[self.collection_name] if database.db is not None else None

    async def enqueue(self, job_type, payload=None, dedupe_key=None, priority=50):
        collection = self.collection
        if collection is None:
            return None
        now = datetime.utcnow()
        if dedupe_key:
            existing = await collection.find_one(
                {"dedupe_key": dedupe_key, "status": {"$in": ["queued", "running", "retrying"]}}
            )
            if existing:
                return str(existing["_id"])
        job_id = str(uuid4())
        await collection.insert_one(
            {
                "_id": job_id,
                "job_type": job_type,
                "payload": payload or {},
                "dedupe_key": dedupe_key,
                "priority": priority,
                "status": "queued",
                "attempts": 0,
                "max_attempts": 3,
                "available_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        return job_id

    async def claim(self, worker_id):
        collection = self.collection
        if collection is None:
            return None
        now = datetime.utcnow()
        stale = now - timedelta(minutes=30)
        return await collection.find_one_and_update(
            {
                "$or": [
                    {"status": {"$in": ["queued", "retrying"]}, "available_at": {"$lte": now}},
                    {"status": "running", "locked_at": {"$lt": stale}},
                ]
            },
            {
                "$set": {"status": "running", "locked_at": now, "locked_by": worker_id, "updated_at": now},
                "$inc": {"attempts": 1},
            },
            sort=[("priority", 1), ("created_at", 1)],
            return_document=True,
        )

    async def finish(self, job_id, status="complete", error=None):
        if self.collection is None:
            return
        await self.collection.update_one(
            {"_id": job_id},
            {"$set": {"status": status, "error": error, "updated_at": datetime.utcnow()}, "$unset": {"locked_at": "", "locked_by": ""}},
        )


jobs = JobRepository()

