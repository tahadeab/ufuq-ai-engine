"""
Pydantic Schemas — مسارات التعلم والدروس والاختبارات.

كل مخرجات التوليد (modules/lessons/assessments) يجب أن تخضع
لهذه المخططات قبل الحفظ أو الإرجاع للـBackend.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LessonCitation(BaseModel):
    chunk_id: str
    source_id: str
    page: Optional[int] = None
    quote: Optional[str] = None


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
    type: str = "mcq"  # mcq | open
    question: str
    options: Optional[List[str]] = None
    answer: str
    rationale: str = ""
    difficulty: str = "medium"  # easy | medium | hard
    citations: List[LessonCitation] = Field(default_factory=list)


class Assessment(BaseModel):
    title: str
    questions: List[AssessmentQuestion] = Field(default_factory=list)


class LearningModule(BaseModel):
    order: int
    title: str
    learning_objectives: List[str] = Field(default_factory=list)
    concepts_covered: List[str] = Field(default_factory=list)
    estimated_hours: float = 1.0
    lessons: List[Lesson] = Field(default_factory=list)
    assessment: Optional[Assessment] = None


class LearningPath(BaseModel):
    source_id: str
    title: str = ""
    description: str = ""
    modules: List[LearningModule] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# JSON Schema لاستخدام LLM في توليد مسار التعلم
LEARNING_PATH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "title": {"type": "string"},
                    "learning_objectives": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "concepts_covered": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "estimated_hours": {"type": "number"},
                },
                "required": ["order", "title", "learning_objectives", "concepts_covered"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "description", "modules"],
    "additionalProperties": False,
}
