"""
Pydantic Schemas — الرسم المعرفي (Knowledge Graph).

المبدأ: الرسم = عقد + حواف + بيانات تحقق خوارزمي.
الـmetadata تحوي نتيجة cycle detection وtopological sort
لأنها ضمانات حتمية وليست احتمالية LLM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.concepts import Concept, Relationship, RELATION_TYPES


class GraphNode(BaseModel):
    id: str
    name: str
    type: str = "concept"
    definition: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str  # enum يتحقق في validator
    confidence: float = 0.8
    evidence: List[str] = Field(default_factory=list)


class GraphMetadata(BaseModel):
    algorithm_validated: bool = False
    cycles_detected: int = 0
    cycles: List[List[str]] = Field(default_factory=list)
    topological_order: List[str] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class KnowledgeGraph(BaseModel):
    graph_id: str
    source_id: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    metadata: GraphMetadata = Field(default_factory=GraphMetadata)

    @property
    def node_names(self) -> Dict[str, str]:
        return {n.id: n.name for n in self.nodes}


GRAPH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "definition": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["id", "name"],
                "additionalProperties": False,
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "relation": {"type": "string", "enum": RELATION_TYPES},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source", "target", "relation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["nodes", "edges"],
    "additionalProperties": False,
}
