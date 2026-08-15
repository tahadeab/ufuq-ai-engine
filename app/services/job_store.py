"""
Job Store — خدمة حفظ واسترجاع حالة المهام.

In-memory (MVP) مع تصميم قابل للترقية إلى Postgres.
كل خطوة من خطوات الـAgent تحدّث حالتها هنا لضمان عدم فقدان السياق.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.agent.state import AgentState
from app.schemas.jobs import Job

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._history: Dict[str, list] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    async def update(self, job_id: str, **fields) -> Optional[Job]:
        job = await self.get(job_id)
        if job is None:
            return None
        for key, value in fields.items():
            setattr(job, key, value)
        job.updated_at = datetime.utcnow().isoformat()
        return job

    async def update_result(self, job_id: str, result) -> None:
        job = await self.get(job_id)
        if job is None:
            return
        job.status = result.status
        job.concepts = result.concepts
        job.relationships = result.relationships
        job.graph = result.graph
        job.learning_path = result.learning_path
        job.lessons = result.lessons
        job.assessments = result.assessments
        job.metrics = result.metrics
        job.quality = result.quality or (result.learning_path or {}).get("quality", {})
        previous = self._history.setdefault(job.source_id, [])
        job.version = len(previous) + 1
        if job.learning_path:
            previous.append({"version": job.version, "job_id": job.job_id, "created_at": job.updated_at, "learning_path": job.learning_path, "quality": job.quality})
        job.progress = {"stage": "completed", "percent": 100, "stages": [
            {"id": "upload", "status": "done"},
            {"id": "extraction", "status": "done"},
            {"id": "concepts", "status": "done"},
            {"id": "graph", "status": "done"},
            {"id": "roadmap", "status": "done"},
        ]}
        job.updated_at = datetime.utcnow().isoformat()

    async def list_jobs(self, limit: int = 20) -> list:
        jobs = sorted(
            self._jobs.values(),
            key=lambda j: j.created_at or "",
            reverse=True,
        )
        return [j.model_dump() for j in jobs[:limit]]


_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
