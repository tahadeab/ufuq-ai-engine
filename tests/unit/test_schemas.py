"""
اختبارات Pydantic Schemas — validation حاسم على مخرجات LLM.
"""

import pytest
from pydantic import ValidationError

from app.agent.state import AgentState
from app.schemas.concepts import (
    CONCEPT_EXTRACTION_SCHEMA,
    CONCEPT_TYPES,
    Concept,
    ExtractionOutput,
    RELATION_TYPES,
    Relationship,
)
from app.schemas.graph import GraphEdge, GraphMetadata, GraphNode, KnowledgeGraph
from app.schemas.jobs import (
    Job,
    JobCreateRequest,
    JobResult,
    ReviewDecision,
)
from app.schemas.learning_path import LEARNING_PATH_SCHEMA, LearningModule, LearningPath


class TestConceptSchema:
    def test_valid_concept(self):
        c = Concept(
            id="c-ml-1",
            name="التعلم الآلي",
            type="topic",
            definition="فرع من الذكاء الاصطناعي",
            source_chunk_ids=["chunk-1"],
            confidence=0.95,
        )
        assert c.name == "التعلم الآلي"
        assert c.confidence == 0.95

    def test_default_confidence(self):
        c = Concept(id="c-1", name="مفهوم", type="concept")
        assert c.confidence == 0.8

    def test_confidence_out_of_bounds(self):
        with pytest.raises(ValidationError):
            Concept(id="c-1", name="مفهوم", type="concept", confidence=1.5)

    def test_extraction_schema_structure(self):
        assert "concepts" in CONCEPT_EXTRACTION_SCHEMA["properties"]
        assert "relationships" in CONCEPT_EXTRACTION_SCHEMA["properties"]

    def test_concept_types_complete(self):
        expected = {"concept", "definition", "skill", "topic", "method",
                    "tool", "example", "assessment"}
        assert expected == set(CONCEPT_TYPES)

    def test_relation_types_complete(self):
        expected = {"prerequisite_of", "part_of", "type_of", "related_to",
                    "depends_on", "example_of", "teaches", "assesses",
                    "generalization_of"}
        assert expected == set(RELATION_TYPES)


class TestRelationshipSchema:
    def test_valid_relationship(self):
        r = Relationship(
            source_concept_id="c-1",
            relation="prerequisite_of",
            target_concept_id="c-2",
            evidence_chunk_ids=["chunk-1"],
            confidence=0.9,
        )
        assert r.relation == "prerequisite_of"

    def test_default_confidence(self):
        r = Relationship(
            source_concept_id="a", relation="related_to", target_concept_id="b"
        )
        assert r.confidence == 0.8

    def test_extraction_schema_rejects_bad_relation(self):
        """الـJSON schema (المستخدم مع LLM) يرفض أنواع علاقات غير معروفة."""
        from app.knowledge.validator import validate_json_schema

        bad = {
            "concepts": [],
            "relationships": [
                {
                    "source_concept_id": "a",
                    "relation": "made_up",
                    "target_concept_id": "b",
                    "evidence_chunk_ids": [],
                }
            ],
        }
        errors = validate_json_schema(bad, CONCEPT_EXTRACTION_SCHEMA)
        assert len(errors) >= 1

    def test_extraction_schema_rejects_missing_required(self):
        from app.knowledge.validator import validate_json_schema

        errors = validate_json_schema(
            {"concepts": [], "relationships": []},
            {"type": "object", "properties": {"concepts": {"type": "array"}},
             "required": ["concepts", "relationships"],
             "additionalProperties": False},
        )
        assert len(errors) >= 1


class TestExtractionOutput:
    def test_valid_output(self):
        out = ExtractionOutput(concepts=[], relationships=[])
        assert out.concepts == []


class TestKnowledgeGraphSchema:
    def test_valid_graph(self):
        node = GraphNode(id="c-1", name="ML", type="topic",
                         definition="د", metadata={})
        edge = GraphEdge(source="c-1", target="c-2", relation="related_to",
                         confidence=0.8, evidence=["c1"])
        graph = KnowledgeGraph(
            graph_id="g-1", source_id="s-1", nodes=[node], edges=[edge],
            metadata=GraphMetadata(node_count=1, edge_count=1),
        )
        assert graph.metadata.node_count == 1
        assert graph.metadata.edge_count == 1


class TestLearningPathSchema:
    def test_valid_path(self):
        module = LearningModule(
            order=1, title="مقدمة", learning_objectives=["يشرح"],
            concepts_covered=["ML"], estimated_hours=1.0,
        )
        path = LearningPath(
            source_id="s-1",
            title="مسار ML",
            modules=[module],
            total_hours=1.0,
            language="ar",
        )
        assert path.modules[0].estimated_hours == 1.0
        assert path.source_id == "s-1"

    def test_learning_path_schema_has_modules(self):
        assert "modules" in LEARNING_PATH_SCHEMA["properties"]


class TestJobSchemas:
    def test_agent_states(self):
        assert AgentState.IDLE.value == "IDLE"
        assert AgentState.COMPLETED.value == "COMPLETED"

    def test_job_defaults(self):
        job = Job(job_id="j-1", source_id="s-1")
        assert job.status == "queued"
        assert job.job_type == "process_source"

    def test_review_decision_valid_values(self):
        for d in ("approve", "revise", "reject"):
            assert ReviewDecision(decision=d).decision == d

    def test_job_result_defaults(self):
        r = JobResult(source_id="s-1", job_id="j-1")
        assert r.status == "review_required"

    def test_job_create_request(self):
        req = JobCreateRequest(source_id="s-1", job_type="generate_path")
        assert req.source_id == "s-1"
        assert req.job_type == "generate_path"
