"""
Pydantic Schemas — إدارة المهام (Jobs) وحالات الـAgent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agent.state import AgentState


JOB_STATUSES = [
    "queued",
    "processing",
    "completed",
    "review_required",
    "failed",
]

AGENT_STATES = [
    "IDLE",
    "PLANNING",
    "EXECUTING",
    "RECOVERING",
    "COMPLETED",
    "FAILED",
]


class PlanStep(BaseModel):
    step: int
    tool: str
    status: str = "pending"          # pending | in_progress | done | failed
    result_summary: Optional[str] = None


class Job(BaseModel):
    job_id: str
    source_id: str
    job_type: str = "process_source"  # process_source | generate_path | ask
    task_type: str = "process_source"
    status: str = "queued"
    state: str = "IDLE"
    plan: List[PlanStep] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    retries_remaining: int = 3
    concepts: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    graph: Optional[Dict[str, Any]] = None
    learning_path: Optional[Dict[str, Any]] = None
    lessons: List[Dict[str, Any]] = Field(default_factory=list)
    assessments: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    quality: Dict[str, Any] = Field(default_factory=dict)
    progress: Dict[str, Any] = Field(default_factory=lambda: {"stage": "queued", "percent": 0, "stages": []})
    version: int = 1
    review_comments: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class JobResult(BaseModel):
    """الاستجابة القياسية من AI Engine إلى Backend."""
    source_id: str
    job_id: str
    status: str = "review_required"
    concepts: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    graph: Optional[Dict[str, Any]] = None
    learning_path: Optional[Dict[str, Any]] = None
    lessons: List[Dict[str, Any]] = Field(default_factory=list)
    assessments: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    quality: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class JobCreateRequest(BaseModel):
    """طلب إنشاء مهمة جديدة عبر POST /jobs."""
    source_id: str
    job_type: str = "process_source"  # process_source | generate_path | ask
    document_title: Optional[str] = None
    query: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ReviewDecision(BaseModel):
    item_id: Optional[str] = None
    item_type: Optional[str] = None  # concept | relationship | module | lesson | question
    decision: str   # approve | revise | reject
    edited_payload: Optional[Dict[str, Any]] = None
    reviewer_note: Optional[str] = None
    comments: Optional[str] = None
