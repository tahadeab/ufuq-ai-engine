"""
Learning Tools — أدوات توليد مسارات التعلم والدروس والاختبارات.

generate_learning_path / generate_module / generate_lesson / generate_assessment
(القسم 4.4 من وثيقة المشروع)

المبدأ: التوليد يُبنى على الترتيب الطوبولوجي الخوارزمي —
LLM يولّد المحتوى فقط، والترتيب والاعتمادات حتمية من الخوارزمية.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.llm.base import LLMMessage
from app.llm.factory import get_llm
from app.llm.prompts import load_prompt
from app.schemas.learning_path import LEARNING_PATH_SCHEMA

logger = logging.getLogger(__name__)


async def generate_learning_path(
    sorted_graph: dict, source_id: str, source_title: str = ""
) -> Dict[str, Any]:
    llm = get_llm()
    order = sorted_graph.get("ordered", []) or sorted_graph.get("metadata", {}).get(
        "topological_order", []
    )
    nodes = sorted_graph.get("nodes", [])
    edges = sorted_graph.get("edges", [])

    node_map = {n.get("id"): n for n in nodes}
    ordered_nodes = [node_map.get(nid) for nid in order if nid in node_map]

    # تجميع المفاهيم في وحدات حسب المستوى الطوبولوجي
    from app.algorithms.topological_sort import topological_levels

    from app.knowledge.graph_builder import DIRECTED_RELATIONS

    adjacency: Dict[str, List[str]] = {n.get("id"): [] for n in nodes}
    for e in edges:
        if e.get("relation") in DIRECTED_RELATIONS:
            adjacency.setdefault(e.get("source"), [])
            adjacency.setdefault(e.get("target"), [])
            adjacency[e.get("source")].append(e.get("target"))
    levels = topological_levels(
        [n.get("id") for n in nodes], adjacency
    )

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for n in ordered_nodes:
        grouped.setdefault(levels.get(n.get("id"), 0), []).append(n)

    modules_spec = []
    for i, (level, concepts) in enumerate(sorted(grouped.items()), start=1):
        modules_spec.append(
            {
                "order": i,
                "level": level,
                "concepts": [
                    {
                        "name": c.get("name"),
                        "definition": c.get("definition"),
                    }
                    for c in concepts
                ],
            }
        )

    prompt = load_prompt(
        "generate_module",
        source_title=source_title,
        modules_spec=json.dumps(modules_spec, ensure_ascii=False, indent=1),
        json_schema=json.dumps(LEARNING_PATH_SCHEMA, ensure_ascii=False, indent=2),
    )
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(
            role="user",
            content="ولّد مسار تعلم بهذه الوحدات. كل وحدة يجب أن تحمل order تسلسلي.",
        ),
    ]

    payload = await llm.generate_json(messages, schema=LEARNING_PATH_SCHEMA, temperature=0.3)
    payload["source_id"] = source_id

    # فرض الترتيب الحتمي: نعيد ترتيب الوحدات حسب order الصحيح
    payload["modules"] = sorted(
        payload.get("modules", []), key=lambda m: m.get("order", 999)
    )
    for i, m in enumerate(payload["modules"], start=1):
        m["order"] = i

    return {"learning_path": payload}


async def generate_lesson(lesson_spec: dict, chunks: list) -> Dict[str, Any]:
    llm = get_llm()
    context_chunks = _format_chunks(chunks, max_chars=6000)

    prompt = load_prompt(
        "generate_lesson",
        lesson_title=lesson_spec.get("title", ""),
        objectives=json.dumps(lesson_spec.get("objectives", []), ensure_ascii=False),
        concepts=json.dumps(lesson_spec.get("concepts", []), ensure_ascii=False),
        source_context=context_chunks,
    )
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(
            role="user",
            content=(
                "اكتب الدرس بالعربية الفصحى مع Markdown. "
                "اسند كل معلومة بأحد المقاطع المقدمة فقط — لا تخترع معلومات."
            ),
        ),
    ]

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "objectives": {"type": "array", "items": {"type": "string"}},
            "body": {"type": "string"},
            "examples": {"type": "array", "items": {"type": "string"}},
            "exercises": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string"},
                        "hint": {"type": "string"},
                    },
                    "required": ["instruction"],
                    "additionalProperties": False,
                },
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "quote": {"type": "string"},
                    },
                    "required": ["chunk_id"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "body", "citations"],
        "additionalProperties": False,
    }

    payload = await llm.generate_json(messages, schema=schema, temperature=0.4)
    return {"lesson": payload}


async def generate_assessment(objectives: list, chunks: list) -> Dict[str, Any]:
    llm = get_llm()
    context_chunks = _format_chunks(chunks, max_chars=8000)

    prompt = load_prompt(
        "generate_assessment",
        objectives=json.dumps(objectives, ensure_ascii=False),
        source_context=context_chunks,
    )
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(
            role="user",
            content=(
                "ولّد اختباراً من 5 أسئلة: 3 اختيار متعدد (mcq) و2 أسئلة مفتوحة. "
                "الإجابة الصحيحة والشرح يجب أن يكونا مستندين للمقاطع فقط."
            ),
        ),
    ]

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["mcq", "open"]},
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "answer": {"type": "string"},
                        "rationale": {"type": "string"},
                        "difficulty": {
                            "type": "string", "enum": ["easy", "medium", "hard"]
                        },
                        "citations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "chunk_id": {"type": "string"},
                                },
                                "required": ["chunk_id"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["type", "question", "answer", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "questions"],
        "additionalProperties": False,
    }

    payload = await llm.generate_json(messages, schema=schema, temperature=0.3)
    return {"assessment": payload}


def _format_chunks(chunks: list, max_chars: int = 6000) -> str:
    """تجميع مقاطع في نص سياقي مختصر للمولدات."""
    parts: List[str] = []
    total = 0
    for c in chunks:
        payload = c.to_payload() if hasattr(c, "to_payload") else dict(c)
        cid = payload.get("chunk_id", "?")
        path = payload.get("heading_path", "")
        text = (payload.get("text", "") or "")[:800]
        block = f"[{cid}] ({path})\n{text}"
        if total + len(block) > max_chars and parts:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)
