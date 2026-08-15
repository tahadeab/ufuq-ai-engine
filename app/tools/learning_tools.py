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
import re
import unicodedata
from typing import Any, Dict, List

from app.llm.base import LLMMessage
from app.llm.factory import get_llm
from app.llm.prompts import load_prompt
from app.schemas.learning_path import ENRICHMENT_SCHEMA

logger = logging.getLogger(__name__)


async def generate_learning_path(
    sorted_graph: dict, source_id: str, source_title: str = "", chunks: list | None = None
) -> Dict[str, Any]:
    """Build a deterministic, grounded roadmap and use the LLM only for wording."""
    chunks = chunks or []
    order = sorted_graph.get("ordered", []) or sorted_graph.get("metadata", {}).get("topological_order", [])
    nodes = sorted_graph.get("nodes", [])
    edges = sorted_graph.get("edges", [])
    if not nodes:
        raise ValueError("KNOWLEDGE_GRAPH_EMPTY: لا يمكن توليد Roadmap من رسم معرفي فارغ")

    node_map = {n.get("id"): n for n in nodes}
    ordered_nodes = [node_map[nid] for nid in order if nid in node_map]
    if len(ordered_nodes) < len(nodes):
        ordered_nodes += [n for n in nodes if n not in ordered_nodes]

    from app.algorithms.topological_sort import topological_levels
    from app.knowledge.graph_builder import DIRECTED_RELATIONS
    adjacency: Dict[str, List[str]] = {n.get("id"): [] for n in nodes}
    for edge in edges:
        if edge.get("relation") in DIRECTED_RELATIONS:
            adjacency.setdefault(edge.get("source"), []).append(edge.get("target"))
    levels = topological_levels([n.get("id") for n in nodes], adjacency)
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for node in ordered_nodes:
        grouped.setdefault(levels.get(node.get("id"), 0), []).append(node)

    chunk_map = {str(c.get("chunk_id")): c for c in chunks if c.get("chunk_id")}
    skeleton = []
    previous_id = None
    for index, (level, concepts) in enumerate(sorted(grouped.items()), start=1):
        module_id = f"module-{index}"
        citations = []
        concept_ids = []
        for concept in concepts:
            concept_ids.append(concept.get("id") or concept.get("name", ""))
            refs = concept.get("source_chunk_ids") or concept.get("evidence_chunk_ids") or []
            for ref in refs[:2]:
                chunk = chunk_map.get(str(ref), {})
                quote = _best_citation_quote(chunk.get("text") or chunk.get("content") or "")
                if quote:
                    citations.append({"source_id": source_id, "chunk_id": str(ref), "quote": quote, "page": chunk.get("page")})
        if not citations and chunks:
            first = chunks[0]
            citations.append({"source_id": source_id, "chunk_id": str(first.get("chunk_id")), "quote": _best_citation_quote(first.get("text") or first.get("content") or ""), "page": first.get("page")})
        skeleton.append({"module_id": module_id, "order": index, "level": level, "concepts_covered": concept_ids, "source_citations": citations, "prerequisite_module_ids": [previous_id] if previous_id else []})
        previous_id = module_id

    modules_spec = [{"module_id": m["module_id"], "concepts": [node_map[cid].get("name", cid) for cid in m["concepts_covered"] if cid in node_map]} for m in skeleton]
    prompt = load_prompt("generate_module", source_title=source_title, modules_spec=json.dumps(modules_spec, ensure_ascii=False), json_schema=json.dumps(ENRICHMENT_SCHEMA, ensure_ascii=False))
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(role="user", content="حسّن صياغة عنوان ووصف وأهداف كل وحدة فقط. لا تغيّر module_id ولا تضف مفاهيم أو مصادر."),
    ]
    enriched = await get_llm().generate_json(messages, schema=ENRICHMENT_SCHEMA, temperature=0.3)
    enriched_by_id = {m.get("module_id"): m for m in enriched.get("modules", [])}
    modules = []
    for item in skeleton:
        text = enriched_by_id.get(item["module_id"], {})
        modules.append({**item, "title": text.get("title") or f"الوحدة {item['order']}", "description": text.get("description", ""), "learning_objectives": text.get("learning_objectives") or [f"فهم {cid}" for cid in item["concepts_covered"]], "estimated_hours": max(1.0, len(item["concepts_covered"]) * 0.5)})
    sample_text = " ".join(str(c.get("text") or c.get("content") or "") for c in chunks[:3])
    language = "ar" if len(re.findall(r"[\u0600-\u06FF]", sample_text)) >= 8 else "en"
    default_title = "خارطة التعلم" if language == "ar" else "Learning Roadmap"
    default_description = ("مسار مبني على الرسم المعرفي والاستشهادات الأصلية." if language == "ar" else "A learning path grounded in the knowledge graph and original citations.")
    payload = {"source_id": source_id, "title": source_title or default_title, "description": default_description, "modules": modules, "metadata": {"generation_method": "deterministic_graph_plus_llm_enrichment", "graph_validated": True, "language": language, "citation_count": sum(len(m.get("source_citations", [])) for m in modules)}}
    from app.knowledge.validator import CitationValidator
    CitationValidator(chunks, source_id).assert_valid(payload)
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


def _best_citation_quote(text: str, max_chars: int = 500) -> str:
    """اختر اقتباساً قابلاً للقراءة مع إزالة آثار PDF وUnicode غير المرئية."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cf", "Cc"} or ch in {"\n", "\t"})
    lines = []
    for line in str(text or "").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("<!--") or clean.startswith("!["):
            continue
        lines.append(clean)
    quote = " ".join(lines)
    return quote[:max_chars].strip()


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
