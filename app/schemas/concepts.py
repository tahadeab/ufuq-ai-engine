"""
Pydantic Schemas — المفاهيم والعلاقات.

هذه الطبقة تنفذ "منطق العمل" الخاص بالكيانات المعرفية:
التحقق من الصلاحية، القيم المسموحة، الافتراضات.
لا تحتوي على أي تقنية (لا LLM، لا DB).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


CONCEPT_TYPES = [
    "concept", "definition", "skill", "topic", "method",
    "tool", "example", "assessment",
]

RELATION_TYPES = [
    "prerequisite_of", "part_of", "type_of", "related_to",
    "depends_on", "example_of", "teaches", "assesses", "generalization_of",
]


class Concept(BaseModel):
    id: str
    name: str
    type: str = "concept"
    definition: Optional[str] = None
    source_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    source_concept_id: str
    relation: str  # يُتحقق منها في GraphValidator
    target_concept_id: str
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ExtractionOutput(BaseModel):
    """مخرج LLM عند استخراج المفاهيم والعلاقات من مقطع/مستند."""
    concepts: List[Concept] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)


# ─── JSON Schemas لاستخدامها مع LLM (response schemas) ────────────────

CONCEPT_EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": CONCEPT_TYPES},
                    "definition": {"type": "string"},
                    "source_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["id", "name", "type", "definition", "source_chunk_ids"],
                "additionalProperties": False,
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_concept_id": {"type": "string"},
                    "relation": {"type": "string", "enum": RELATION_TYPES},
                    "target_concept_id": {"type": "string"},
                    "evidence_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "source_concept_id", "relation",
                    "target_concept_id", "evidence_chunk_ids",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["concepts", "relationships"],
    "additionalProperties": False,
}
