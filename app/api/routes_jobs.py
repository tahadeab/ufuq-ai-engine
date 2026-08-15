"""
Routes: Jobs — إدارة مهام الـAgent.

POST /jobs          → إنشاء مهمة (process_source / generate_path)
GET  /jobs/{id}     → حالة المهمة
GET  /jobs          → قائمة المهام
POST /jobs/{id}/review → قرار المراجعة البشرية
"""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agent.orchestrator import get_agent
from app.agent.state import AgentState
from app.schemas.jobs import (
    Job,
    JobCreateRequest,
    ReviewDecision,
)
from app.services.job_store import get_job_store

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=Job)
async def create_job(request: JobCreateRequest, background: BackgroundTasks) -> Job:
    """
    إنشاء مهمة جديدة وتشغيلها في الخلفية.
    - process_source: دورة كاملة (Ingestion → RAG → Concepts → Graph → Path → Lessons)
    - generate_path: توليد مسار تعلم فقط
    """
    job_store = get_job_store()
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    job = Job(
        job_id=job_id,
        source_id=request.source_id,
        job_type=request.job_type,
        status="processing",
        state=AgentState.IDLE,
    )
    await job_store.save(job)

    background.add_task(run_job_background, job_id=job_id, request=request)
    return job


async def run_job_background(job_id: str, request: JobCreateRequest) -> None:
    job_store = get_job_store()
    agent = get_agent()

    await job_store.update(job_id, status="processing", state=AgentState.PLANNING, progress={"stage": "planning", "percent": 10, "stages": [{"id": "upload", "status": "done"}, {"id": "extraction", "status": "in_progress"}, {"id": "concepts", "status": "pending"}, {"id": "graph", "status": "pending"}, {"id": "roadmap", "status": "pending"}]})
    try:
        extra_context = {
            "document_title": request.document_title or "",
            "search_query": request.query or "",
            **(request.context or {}),
        }
        await job_store.update(job_id, progress={"stage": "knowledge_processing", "percent": 45, "stages": [{"id": "upload", "status": "done"}, {"id": "extraction", "status": "done"}, {"id": "concepts", "status": "in_progress"}, {"id": "graph", "status": "pending"}, {"id": "roadmap", "status": "pending"}]})
        result = await agent.run_task(
            job_id=job_id,
            source_id=request.source_id,
            task_type=request.job_type,
            extra_context=extra_context,
        )
        await job_store.update_result(job_id, result)
        if result.learning_path and result.learning_path.get("quality", {}).get("review_required"):
            await job_store.update(job_id, status="review_required")
    except Exception as exc:
        await job_store.update(
            job_id, status="failed", error="PROCESSING_FAILED",
            metrics={"error": str(exc)},
            progress={"stage": "failed", "percent": 0, "stages": []},
        )


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job_store = get_job_store()
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="مهمة غير موجودة")
    return job


@router.get("", response_model=list)
async def list_jobs(limit: int = 20) -> list:
    job_store = get_job_store()
    return await job_store.list_jobs(limit=limit)


@router.post("/{job_id}/review")
async def review_job(job_id: str, decision: ReviewDecision) -> Dict:
    """قرار المراجعة البشرية على نواتج المهمة (approve/revise/reject)."""
    job_store = get_job_store()
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="مهمة غير موجودة")
    if job.status != "review_required":
        raise HTTPException(
            status_code=400, detail="المهمة ليست في حالة انتظار المراجعة"
        )

    if decision.decision == "approve":
        await job_store.update(job_id, status="approved")
    elif decision.decision == "revise":
        await job_store.update(job_id, status="revision_requested",
                               review_comments=decision.comments)
        # تشغيل إعادة معالجة خفيفة
        background = BackgroundTasks()
        await run_job_background(job_id=job_id,
                                 request=JobCreateRequest(source_id=job.source_id))
    else:  # reject
        await job_store.update(job_id, status="rejected",
                               review_comments=decision.comments)

    return {"job_id": job_id, "decision": decision.decision}
