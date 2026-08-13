"""
Agent State — حالة الـAgent ونموذج الذاكرة.

```text
IDLE ──▶ PLANNING ──▶ EXECUTING ◄──▶ RECOVERING
                  └──▶ COMPLETED (review_required)
                  └──▶ FAILED (تقرير خطأ)
```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


VALID_TRANSITIONS = {
    AgentState.IDLE: {AgentState.PLANNING},
    AgentState.PLANNING: {AgentState.EXECUTING, AgentState.FAILED},
    AgentState.EXECUTING: {
        AgentState.EXECUTING,
        AgentState.RECOVERING,
        AgentState.COMPLETED,
        AgentState.FAILED,
    },
    AgentState.RECOVERING: {AgentState.EXECUTING, AgentState.FAILED},
    AgentState.COMPLETED: {AgentState.IDLE},
    AgentState.FAILED: {AgentState.IDLE},
}


@dataclass
class PlanStep:
    step: int
    tool: str
    description: str = ""
    status: str = "pending"          # pending | in_progress | done | failed
    result_summary: str = ""


@dataclass
class AgentMemory:
    """الذاكرة الكاملة لمهمة واحدة — تُحفظ في Job context."""

    task_id: str
    state: AgentState = AgentState.IDLE
    plan: List[PlanStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    retries_remaining: int = 3
    current_step: int = 0
    error_log: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # حقول نتائج
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    concepts: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    graph: Dict[str, Any] = field(default_factory=dict)
    learning_path: Dict[str, Any] = field(default_factory=dict)
    lessons: List[Dict[str, Any]] = field(default_factory=list)
    assessments: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "plan": [
                {"step": s.step, "tool": s.tool, "status": s.status,
                 "result_summary": s.result_summary}
                for s in self.plan
            ],
            "context": self.context,
            "retries_remaining": self.retries_remaining,
            "current_step": self.current_step,
            "error_log": self.error_log,
            "created_at": self.created_at,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def transition(self, new_state: AgentState) -> None:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise RuntimeError(
                f"انتقال غير صالح: {self.state.value} → {new_state.value}"
            )
        logger.info("Agent transition: %s → %s", self.state.value, new_state.value)
        self.state = new_state
        self.updated_at = datetime.utcnow().isoformat()
