"""
Ufuq Learning Architect Agent — Orchestrator الرئيسي.

Single Orchestrator فوق طبقة الأدوات (منطق حلقة التنفيذ):
IDLE → PLANNING → EXECUTING(خطوة بخطوة مع تحقق) → RECOVERING عند الفشل
→ COMPLETED(review_required) أو FAILED مع تقرير.

المبدأ: الأدوات الحتمية أولاً، والـAgent منسق فوقها.
كل خطوة تُنفَّذ مرة واحدة ثم يعاد التقييم — لا تنفيذ جماعي.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, Optional

from app.agent.policy import AgentPolicy
from app.agent.state import AgentMemory, AgentState, PlanStep
from app.config import get_settings
from app.schemas.jobs import JobResult
from app.tools import (
    document_tools,
    knowledge_tools,
    learning_tools,
    rag_tools,
)
from app.tools.registry import get_registry

logger = logging.getLogger(__name__)


# تعيين الأدوات إلى معالجاتها
TOOL_HANDLERS = {
    "get_source": document_tools.get_source,
    "parse_source": document_tools.parse_source,
    "get_document_structure": document_tools.get_document_structure,
    "get_chunks": document_tools.get_chunks,
    "semantic_search": rag_tools.semantic_search,
    "keyword_search": rag_tools.keyword_search,
    "hybrid_search": rag_tools.hybrid_search,
    "rerank_results": rag_tools.rerank_results,
    "extract_concepts": knowledge_tools.extract_concepts,
    "extract_relationships": knowledge_tools.extract_relationships,
    "merge_concepts": knowledge_tools.merge_concepts,
    "build_graph": knowledge_tools.build_graph,
    "validate_graph": knowledge_tools.validate_graph,
    "detect_cycles": knowledge_tools.detect_cycles,
    "topological_sort": knowledge_tools.topological_sort,
    "generate_learning_path": learning_tools.generate_learning_path,
    "generate_lesson": learning_tools.generate_lesson,
    "generate_assessment": learning_tools.generate_assessment,
}


class UfuqAgent:
    """
    Ufuq Learning Architect Agent.
    لا يستدعي أي LLM أو DB مباشرة — فقط عبر الأدوات.
    """

    def __init__(self):
        settings = get_settings()
        self.max_retries = settings.agent_max_retries
        self.max_steps = settings.agent_max_steps
        self.policy = AgentPolicy()

    async def run_task(
        self,
        job_id: str,
        source_id: str,
        task_type: str = "process_source",
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> JobResult:
        start = time.time()
        memory = AgentMemory(task_id=job_id)
        memory.context = {
            "source_id": source_id,
            "task_type": task_type,
            **(extra_context or {}),
        }

        try:
            # ── 1. التخطيط ───────────────────────────────────
            memory.transition(AgentState.PLANNING)
            plan_steps = self.policy.build_plan(task_type)
            memory.plan = [
                PlanStep(step=i + 1, tool=s["tool"], description=s["description"])
                for i, s in enumerate(plan_steps)
            ]

            # ── 2. التنفيذ خطوة بخطوة ───────────────────────
            memory.transition(AgentState.EXECUTING)
            step = 0
            while memory.state == AgentState.EXECUTING:
                step += 1
                if step > self.max_steps:
                    raise RuntimeError(f"تجاوز الحد الأقصى للخطوات ({self.max_steps})")

                if memory.current_step >= len(memory.plan):
                    memory.transition(AgentState.COMPLETED)
                    break

                plan_step = memory.plan[memory.current_step]
                plan_step.status = "in_progress"

                success = await self._execute_step(memory, plan_step)
                if success:
                    plan_step.status = "done"
                    memory.current_step += 1
                    memory.retries_remaining = self.max_retries  # إعادة ضبط
                else:
                    plan_step.status = "failed"
                    memory.retries_remaining -= 1
                    action = self.policy.decide_on_step_failure(
                        memory.retries_remaining,
                        memory.current_step,
                        len(memory.plan),
                        is_last_step=(memory.current_step == len(memory.plan) - 1),
                    )
                    if action.action == "retry":
                        memory.error_log.append(
                            f"الخطوة {plan_step.step} ({plan_step.tool}): إعادة محاولة — {action.message}"
                        )
                        logger.info("retry: %s", action.message)
                    elif action.action == "fallback":
                        memory.transition(AgentState.RECOVERING)
                        recovered = await self._recover(memory, plan_step)
                        memory.transition(AgentState.EXECUTING)
                        if recovered:
                            plan_step.status = "done"
                            memory.current_step += 1
                            memory.retries_remaining = self.max_retries
                        else:
                            plan_step.result_summary = f"فشل البديل: {action.message}"
                            memory.transition(AgentState.FAILED)
                    else:
                        memory.error_log.append(
                            f"الخطوة {plan_step.step} ({plan_step.tool}): فشل حاسم"
                        )
                        memory.transition(AgentState.FAILED)

            # ── 3. النتيجة ────────────────────────────────────
            elapsed = round(time.time() - start, 1)
            memory.metrics = {
                "processing_time_seconds": elapsed,
                "chunk_count": len(memory.chunks),
                "concept_count": len(memory.concepts),
                "avg_confidence": self._avg_confidence(memory.concepts),
            }

            if memory.error_log:
                memory.metrics["error_log"] = " | ".join(memory.error_log[-5:])
            return JobResult(
                source_id=source_id,
                job_id=job_id,
                status="review_required" if memory.state == AgentState.COMPLETED else "failed",
                concepts=memory.concepts,
                relationships=memory.relationships,
                graph=memory.graph,
                learning_path=memory.learning_path,
                lessons=memory.lessons,
                assessments=memory.assessments,
                metrics=memory.metrics,
            )

        except Exception as exc:
            logger.exception("فشل المهمة %s", job_id)
            memory.state = AgentState.FAILED
            memory.error = str(exc)
            return JobResult(
                source_id=source_id,
                job_id=job_id,
                status="failed",
                metrics={"error": str(exc)},
            )

    async def _execute_step(self, memory: AgentMemory, plan_step: PlanStep) -> bool:
        handler = TOOL_HANDLERS.get(plan_step.tool)
        if handler is None:
            memory.error_log.append(f"أداة غير معروفة: {plan_step.tool}")
            return False

        try:
            arguments = self._build_arguments(memory, plan_step.tool)
            result = await handler(**arguments)
            self._store_step_result(memory, plan_step.tool, result)
            plan_step.result_summary = _summarize(result)
            return True
        except Exception:
            memory.error_log.append(
                f"خطأ في {plan_step.tool}: {traceback.format_exc(limit=0).strip().splitlines()[-1]}"
            )
            return False

    def _build_arguments(self, memory: AgentMemory, tool: str) -> Dict[str, Any]:
        src = memory.context.get("source_id", "")
        base = {}
        if tool in ("get_source", "parse_source", "get_document_structure",
                    "get_chunks", "semantic_search", "keyword_search", "hybrid_search"):
            base["source_id"] = src
        if tool in ("get_chunks",):
            base["limit"] = 2000
        if tool in ("semantic_search", "keyword_search", "hybrid_search"):
            base["query"] = memory.context.get("search_query", "ما المفاهيم الرئيسية في هذا المستند؟")
            base["top_k"] = 10
        if tool in ("extract_concepts",):
            base["chunks"] = memory.chunks or memory.context.get("chunks", [])
            base["document_title"] = memory.context.get("document_title", "")
        if tool in ("extract_relationships",):
            base["concepts"] = memory.concepts or memory.context.get("concepts", [])
            base["chunks"] = memory.chunks or memory.context.get("chunks", [])
            base["document_title"] = memory.context.get("document_title", "")
        if tool == "build_graph":
            base["concepts"] = memory.concepts
            base["relationships"] = memory.relationships
            base["source_id"] = src
        if tool in ("validate_graph", "detect_cycles", "topological_sort"):
            base["graph"] = memory.graph
        if tool == "generate_learning_path":
            base["sorted_graph"] = memory.graph
            base["source_id"] = src
            base["source_title"] = memory.context.get("document_title", "")
        if tool == "generate_lesson":
            base["lesson_spec"] = memory.context.get("lesson_spec", {
                "title": "درس تمهيدي",
                "objectives": [],
                "concepts": [],
            })
            base["chunks"] = memory.chunks
        if tool == "generate_assessment":
            base["objectives"] = memory.context.get("objectives", [])
            base["chunks"] = memory.chunks
        # دمج السياق الإضافي
        ctx_tool_args = memory.context.get(f"args_{tool}", {})
        base.update(ctx_tool_args)
        return base

    def _store_step_result(self, memory: AgentMemory, tool: str, result: Any) -> None:
        r = result if isinstance(result, dict) else {}
        if tool == "get_chunks":
            memory.chunks = r.get("chunks", [])
        elif tool == "extract_concepts":
            memory.concepts = r.get("concepts", [])
            memory.context["candidate_concepts"] = r.get("count", 0)
        elif tool == "extract_relationships":
            memory.relationships = r.get("relationships", [])
        elif tool == "build_graph":
            memory.graph = r.get("graph", {})
            memory.context["graph_issues"] = r.get("issues", [])
        elif tool == "generate_learning_path":
            memory.learning_path = r.get("learning_path", {})
            memory.context["objectives"] = [
                obj for m in memory.learning_path.get("modules", [])
                for obj in m.get("learning_objectives", [])
            ]
        elif tool == "generate_lesson":
            memory.lessons.append(r.get("lesson", {}))
        elif tool == "generate_assessment":
            memory.assessments.append(r.get("assessment", {}))

    async def _recover(self, memory: AgentMemory, plan_step: PlanStep) -> bool:
        """مسار استرداد بسيط: تخطي الخطوة الفاشلة غير الحرجة."""
        critical_tools = {"build_graph", "generate_learning_path"}
        if plan_step.tool in critical_tools:
            memory.error_log.append(f"الاسترداد فشل: أداة حرجة {plan_step.tool}")
            return False
        memory.error_log.append(
            f"استرداد بتخطي أداة {plan_step.tool} — المتابعة للخطوة التالية"
        )
        plan_step.status = "skipped"
        return True

    @staticmethod
    def _avg_confidence(concepts: list) -> float:
        if not concepts:
            return 0.0
        return round(
            sum(c.get("confidence", 0.8) for c in concepts) / len(concepts), 3
        )


_agent_instance: Optional[UfuqAgent] = None


def get_agent() -> UfuqAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = UfuqAgent()
    return _agent_instance


def _summarize(result: Any) -> str:
    if isinstance(result, dict):
        count = result.get("count")
        return f"success (count={count})" if count is not None else "success"
    return "success"
