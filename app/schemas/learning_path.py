"""Schemas for grounded learning roadmaps."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class LessonCitation(BaseModel):
    chunk_id: str
    source_id: str
    page: Optional[int] = None
    quote: Optional[str] = None

class SourceCitation(BaseModel):
    source_id: str
    chunk_id: str
    quote: str
    page: Optional[int] = None

class Exercise(BaseModel):
    instruction: str
    hint: Optional[str] = None

class Lesson(BaseModel):
    title: str
    objectives: List[str] = Field(default_factory=list)
    body: str = ""
    examples: List[str] = Field(default_factory=list)
    citations: List[LessonCitation] = Field(default_factory=list)
    exercises: List[Exercise] = Field(default_factory=list)

class AssessmentQuestion(BaseModel):
    type: str = "mcq"
    question: str
    options: Optional[List[str]] = None
    answer: str
    rationale: str = ""
    difficulty: str = "medium"
    citations: List[LessonCitation] = Field(default_factory=list)

class Assessment(BaseModel):
    title: str
    questions: List[AssessmentQuestion] = Field(default_factory=list)

class LearningModule(BaseModel):
    order: int
    module_id: str
    title: str
    description: str = ""
    prerequisite_module_ids: List[str] = Field(default_factory=list)
    learning_objectives: List[str] = Field(default_factory=list)
    concepts_covered: List[str] = Field(default_factory=list)
    estimated_hours: float = 1.0
    source_citations: List[SourceCitation] = Field(default_factory=list)
    lessons: List[Lesson] = Field(default_factory=list)
    assessment: Optional[Assessment] = None

class LearningPath(BaseModel):
    source_id: str
    title: str = ""
    description: str = ""
    modules: List[LearningModule] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# The model only enriches language. Ordering, concepts and citations are deterministic.
ENRICHMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "module_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "learning_objectives": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["module_id", "title", "description", "learning_objectives"],
            },
        }
    },
    "required": ["modules"],
}

# Compatibility alias for existing imports; new code should use ENRICHMENT_SCHEMA.
LEARNING_PATH_SCHEMA = ENRICHMENT_SCHEMA
