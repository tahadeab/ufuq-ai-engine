"""
Knowledge Extractor — استخراج المفاهيم والعلاقات عبر LLM.

المبدأ: LLM هو أداة استخراج فقط. كل مخرجه يمر بـ JSON Schema validation
والتحقق من المراجع (أن chunk_id موجود فعلاً في المدخلات).
لا LLM بدون schema — Structured Outputs إجبارية.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from app.llm.base import LLMMessage
from app.llm.factory import get_llm
from app.llm.prompts import load_prompt
from app.schemas.concepts import (
    Concept,
    CONCEPT_EXTRACTION_SCHEMA,
    CONCEPT_TYPES,
    Relationship,
)

logger = logging.getLogger(__name__)

# prefix آمن لتوليد IDs مستقرة من أسماء المفاهيم
_NAME_TO_ID: Dict[str, str] = {}


def concept_id_from_name(name: str, counter: Dict[str, int]) -> str:
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", name.strip().lower())[:30].strip("-") or "concept"
    counter[slug] = counter.get(slug, 0) + 1
    return f"c-{slug}-{counter[slug]}"


class KnowledgeExtractor:
    """استخراج مفاهيم وعلاقات من مقاطع مستند."""

    def __init__(self):
        self.llm = get_llm()
        self._name_counter: Dict[str, int] = {}

    # ─────────────────────────────────────────
    # استخراج المفاهيم من مجموعة مقاطع
    # ─────────────────────────────────────────
    async def extract_concepts_from_chunks(
        self, chunks: List[Dict[str, Any]], document_title: str = ""
    ) -> List[Concept]:
        if not chunks:
            return []

        all_concepts: Dict[str, Concept] = {}

        for chunk in chunks:
            try:
                concepts = await self._extract_one_chunk(
                    chunk=chunk, document_title=document_title
                )
            except Exception:
                logger.exception(
                    "فشل استخراج المفاهيم من chunk %s", chunk.get("chunk_id")
                )
                continue

            for c in concepts:
                # إدماج التكرارات بنفس الاسم داخل نفس المصدر
                if c.name in all_concepts:
                    existing = all_concepts[c.name]
                    existing.source_chunk_ids = sorted(
                        set(existing.source_chunk_ids) | set(c.source_chunk_ids)
                    )
                    existing.confidence = max(existing.confidence, c.confidence)
                else:
                    all_concepts[c.name] = c

        return list(all_concepts.values())

    async def _extract_one_chunk(
        self, chunk: Dict[str, Any], document_title: str
    ) -> List[Concept]:
        chunk_id = chunk.get("chunk_id", "unknown")
        schema_with_ids = self._inject_chunk_ids(CONCEPT_EXTRACTION_SCHEMA, chunk_id)

        prompt = load_prompt(
            "extract_concepts",
            document_title=document_title,
            chunk_text=chunk.get("text", ""),
            json_schema=json.dumps(schema_with_ids, ensure_ascii=False, indent=2),
            chunk_id=chunk_id,
            heading_path=chunk.get("heading_path", ""),
        )

        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(
                role="user",
                content=(
                    "استخرج المفاهيم من هذا المقطع. "
                    "إذا لم تجد مفاهيم كافية، أعد مصفوفة مفاهيم فارغة مع مصفوفة علاقات فارغة."
                ),
            ),
        ]

        payload = await self.llm.generate_json(
            messages, schema=schema_with_ids, temperature=0.1
        )
        return self._validate_concepts(payload, chunk)

    def _validate_concepts(
        self, payload: Dict[str, Any], chunk: Dict[str, Any]
    ) -> List[Concept]:
        """تنظيف المدخلات الملوثة: إسقاط المفاهيم بمراجع زائفة."""
        chunk_id = chunk.get("chunk_id", "")
        concepts: List[Concept] = []
        for item in payload.get("concepts", []) or []:
            refs = item.get("source_chunk_ids") or []
            if chunk_id and chunk_id not in refs:
                refs = [chunk_id]
            concept = Concept(
                id=item.get("id") or concept_id_from_name(
                    item.get("name", ""), self._name_counter
                ),
                name=(item.get("name") or "").strip(),
                type=item.get("type") if item.get("type") in CONCEPT_TYPES else "concept",
                definition=(item.get("definition") or "").strip(),
                source_chunk_ids=refs,
                confidence=float(item.get("confidence", 0.8)),
            )
            if not concept.name:
                continue
            concepts.append(concept)
        return concepts

    # ─────────────────────────────────────────
    # استخراج العلاقات بين المفاهيم
    # ─────────────────────────────────────────
    async def extract_relationships(
        self,
        concepts: List[Concept],
        chunks: List[Dict[str, Any]],
        document_title: str = "",
    ) -> List[Relationship]:
        if not concepts or not chunks:
            return []

        concept_map = {c.name: c.id for c in concepts}
        concept_by_id = {c.id: c for c in concepts}
        all_rels: Dict[str, Relationship] = {}

        # نجمع المفاهيم ذات الصلة مع كل chunk لتقليل تكلفة الاستدعاءات
        # (كل chunk يعالَج مرة واحدة مع قائمة مفاهيم مستخرجة منه)
        for chunk in chunks:
            refs = set(chunk.get("source_chunk_ids", [])) or {chunk.get("chunk_id", "")}
            related = [c for c in concepts if set(c.source_chunk_ids) & refs]
            if len(related) < 2:
                continue

            try:
                rels = await self._extract_relationships_one_chunk(
                    chunk=chunk,
                    concepts=related,
                    document_title=document_title,
                )
            except Exception:
                logger.exception(
                    "فشل استخراج العلاقات من chunk %s", chunk.get("chunk_id")
                )
                continue

            for r in rels:
                key = (r.source_concept_id, r.relation, r.target_concept_id)
                if key in all_rels:
                    existing = all_rels[key]
                    existing.confidence = max(existing.confidence, r.confidence)
                    existing.evidence_chunk_ids = sorted(
                        set(existing.evidence_chunk_ids) | set(r.evidence_chunk_ids)
                    )
                else:
                    all_rels[key] = r

        # التحقق النهائي: أن طرفي العلاقة موجودان في قائمة المفاهيم
        valid_ids = set(concept_by_id)
        return [
            r for r in all_rels.values()
            if r.source_concept_id in valid_ids and r.target_concept_id in valid_ids
        ]

    async def _extract_relationships_one_chunk(
        self, chunk: Dict[str, Any], concepts: List[Concept], document_title: str
    ) -> List[Relationship]:
        chunk_id = chunk.get("chunk_id", "")
        concepts_json = json.dumps(
            [
                {"id": c.id, "name": c.name, "type": c.type, "definition": c.definition}
                for c in concepts
            ],
            ensure_ascii=False,
            indent=1,
        )

        prompt = load_prompt(
            "extract_relationships",
            document_title=document_title,
            chunk_text=chunk.get("text", ""),
            concepts_json=concepts_json,
            heading_path=chunk.get("heading_path", ""),
        )

        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(
                role="user",
                content="استخرج العلاقات بين المفاهيم المعطاة المدعومة بهذا المقطع.",
            ),
        ]

        schema_with_ids = {
            **CONCEPT_EXTRACTION_SCHEMA,
            "properties": {
                "relationships": CONCEPT_EXTRACTION_SCHEMA["properties"]["relationships"],
            },
            "required": ["relationships"],
            "additionalProperties": False,
        }

        payload = await self.llm.generate_json(
            messages, schema=schema_with_ids, temperature=0.1
        )

        rels: List[Relationship] = []
        for item in payload.get("relationships", []) or []:
            refs = item.get("evidence_chunk_ids") or []
            if chunk_id and chunk_id not in refs:
                refs = [chunk_id]
            rels.append(
                Relationship(
                    source_concept_id=item.get("source_concept_id", ""),
                    relation=item.get("relation", "related_to"),
                    target_concept_id=item.get("target_concept_id", ""),
                    evidence_chunk_ids=refs,
                    confidence=float(item.get("confidence", 0.8)),
                )
            )
        return rels

    @staticmethod
    def _inject_chunk_ids(schema: Dict[str, Any], chunk_id: str) -> Dict[str, Any]:
        import copy

        s = copy.deepcopy(schema)
        items = s["properties"]["concepts"]["items"]
        items["properties"]["source_chunk_ids"] = {
            "type": "array",
            "items": {"type": "string", "const": chunk_id},
        }
        rel_items = s["properties"]["relationships"]["items"]
        rel_items["properties"]["evidence_chunk_ids"] = {
            "type": "array",
            "items": {"type": "string", "const": chunk_id},
        }
        return s
