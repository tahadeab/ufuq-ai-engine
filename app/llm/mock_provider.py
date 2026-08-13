"""
MockLLMProvider — مزوّد اختباري لا يتصل بأي خدمة خارجية.

يستخدم لاختبار تدفق الـAgent والمعالجة الكاملة في بيئات CI
أو الأجهزة التي لا تتوفر فيها Ollama. يعيد استجابات مبنية على
قالب JSON ثابت يمرّر التحقق الصارم (JSON Schema validation).

MockLLMProvider — a test provider that never contacts external
services. Used to exercise the full Agent pipeline in CI or on
machines without Ollama. Returns schema-valid canned responses.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

MOCK_CALL_COUNT: int = 0


class MockLLMProvider(LLMProvider):
    """مزوّد وهمي للاختبار — لا يستدعي أي LLM حقيقي."""

    def __init__(self) -> None:
        self.call_log: list[str] = []

    # ── واجهة LLMProvider ─────────────────────────────────────
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.call_log.append("generate")
        return LLMResponse(content="OK")

    async def generate_json(
        self,
        messages: list[LLMMessage],
        schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        full_text = " ".join(m.content for m in messages)
        kind = self._classify(full_text)
        self.call_log.append(kind)
        global MOCK_CALL_COUNT
        MOCK_CALL_COUNT += 1
        return self._canned(kind)

    async def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float = 0.2,
    ) -> LLMResponse:
        self.call_log.append("generate_with_tools")
        return LLMResponse(content="OK")

    async def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"

    # ── داخلي ──────────────────────────────────────────────────
    def _classify(self, text: str) -> str:
        t = text.lower()
        if "مفهوم" in t or "concept" in t and ("تعريف" in t or "definition" in t):
            return "extract_concepts"
        if "relationship" in t or "علاق" in t:
            return "extract_relationships"
        if "module" in t or "وحدة" in t or "مسار" in t or "path" in t:
            return "generate_module"
        if "lesson" in t or "درس" in t:
            return "generate_lesson"
        if "assessment" in t or "question" in t or "سؤال" in t:
            return "generate_assessment"
        if "valid" in t and "concept" in t:
            return "validate"
        return "summarize"

    def _canned(self, kind: str) -> dict:
        if kind == "extract_concepts":
            return {
                "concepts": [
                    {
                        "id": f"c-{uuid.uuid4().hex[:8]}",
                        "name": "Machine Learning",
                        "definition": "A branch of AI that learns patterns from data.",
                        "type": "concept",
                        "source_chunk_ids": [],
                        "confidence": 0.9,
                    },
                    {
                        "id": f"c-{uuid.uuid4().hex[:8]}",
                        "name": "Supervised Learning",
                        "definition": "Learning with labeled examples.",
                        "type": "concept",
                        "source_chunk_ids": [],
                        "confidence": 0.85,
                    },
                ],
            }
        if kind == "extract_relationships":
            return {
                "relationships": [
                    {
                        "from_concept_id": "",
                        "to_concept_id": "",
                        "type": "prerequisite",
                        "strength": 0.8,
                        "evidence": "Both relate to learning from data.",
                    },
                ],
            }
        if kind == "generate_module":
            return {
                "title": "Introduction to Machine Learning",
                "description": "Foundations of learning from data.",
                "order": 1,
                "estimated_minutes": 30,
                "learning_objectives": ["Understand supervised learning"],
            }
        if kind == "generate_lesson":
            return {
                "title": "What is Machine Learning?",
                "content": "Machine learning lets systems learn from data.",
                "citations": [],
            }
        if kind == "generate_assessment":
            return {
                "questions": [
                    {
                        "question": "What does ML learn from?",
                        "options": ["Data", "Random noise", "Nothing", "Hardware"],
                        "correct_index": 0,
                    },
                ],
            }
        if kind == "validate":
            return {"valid": True, "issues": []}
        return {"summary": "Core ML concepts are discussed."}
