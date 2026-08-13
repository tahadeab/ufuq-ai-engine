"""
اختبارات Knowledge — Graph Builder وTool Registry.
"""

import pytest

from app.knowledge.graph_builder import DIRECTED_RELATIONS, GraphBuilder
from app.schemas.concepts import Concept, Relationship


async def echo_handler(text: str):
    return {"out": text}


class TestGraphBuilder:
    def setup_method(self):
        self.builder = GraphBuilder()
        self.concepts = [
            Concept(id="c-1", name="برمجة", type="skill", definition="د",
                    source_chunk_ids=["c1"], confidence=0.9),
            Concept(id="c-2", name="بايثون", type="tool", definition="د",
                    source_chunk_ids=["c1"], confidence=0.9),
            Concept(id="c-3", name="ذكاء اصطناعي", type="topic", definition="د",
                    source_chunk_ids=["c1"], confidence=0.9),
        ]

    def test_build_valid_graph(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="related_to",
                         target_concept_id="c-2", evidence_chunk_ids=["c1"],
                         confidence=0.8),
        ]
        graph, issues = self.builder.build(self.concepts, rels, source_id="s-1")
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 1
        assert graph.metadata.algorithm_validated
        assert graph.metadata.node_count == 3

    def test_rejects_low_confidence(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="related_to",
                         target_concept_id="c-2", evidence_chunk_ids=["c1"],
                         confidence=0.4),
        ]
        graph, issues = self.builder.build(self.concepts, rels, source_id="s-1")
        assert len(graph.edges) == 0
        assert any("ثقة منخفضة" in i for i in issues)

    def test_rejects_invalid_relation_type(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="bad_type",
                         target_concept_id="c-2", evidence_chunk_ids=["c1"],
                         confidence=0.8),
        ]
        graph, issues = self.builder.build(self.concepts, rels, source_id="s-1")
        assert len(graph.edges) == 0

    def test_rejects_missing_nodes(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="related_to",
                         target_concept_id="c-999", evidence_chunk_ids=["c1"],
                         confidence=0.8),
        ]
        graph, issues = self.builder.build(self.concepts, rels, source_id="s-1")
        assert len(graph.edges) == 0

    def test_cycle_detected_and_reported(self):
        concepts = [
            Concept(id="a", name="A", type="concept", definition="د",
                    source_chunk_ids=["c1"], confidence=0.9),
            Concept(id="b", name="B", type="concept", definition="د",
                    source_chunk_ids=["c1"], confidence=0.9),
        ]
        rels = [
            Relationship(source_concept_id="a", relation="prerequisite_of",
                         target_concept_id="b", evidence_chunk_ids=["c1"],
                         confidence=0.9),
            Relationship(source_concept_id="b", relation="prerequisite_of",
                         target_concept_id="a", evidence_chunk_ids=["c1"],
                         confidence=0.9),
        ]
        graph, issues = self.builder.build(concepts, rels, source_id="s-1")
        assert graph.metadata.cycles_detected > 0
        assert any("دورة" in i for i in issues)

    def test_topological_order_respects_prerequisites(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="prerequisite_of",
                         target_concept_id="c-3", evidence_chunk_ids=["c1"],
                         confidence=0.9),
        ]
        graph, _ = self.builder.build(self.concepts, rels, source_id="s-1")
        order = graph.metadata.topological_order
        assert order.index("c-1") < order.index("c-3")

    def test_undirected_not_in_adjacency(self):
        rels = [
            Relationship(source_concept_id="c-1", relation="related_to",
                         target_concept_id="c-2", evidence_chunk_ids=["c1"],
                         confidence=0.8),
        ]
        graph, _ = self.builder.build(self.concepts, rels, source_id="s-1")
        order = graph.metadata.topological_order
        # related_to لا يفرض ترتيباً
        assert len(order) == 3


class TestDirectRelations:
    def test_directed_types(self):
        assert "prerequisite_of" in DIRECTED_RELATIONS
        assert "depends_on" in DIRECTED_RELATIONS
        assert "part_of" in DIRECTED_RELATIONS
        assert "type_of" in DIRECTED_RELATIONS
        assert "related_to" not in DIRECTED_RELATIONS


class TestToolRegistry:
    @pytest.mark.asyncio
    async def test_register_and_get(self):
        from app.tools.registry import RegisteredTool, ToolRegistry

        reg = ToolRegistry()
        reg.register(RegisteredTool(
            name="echo", description="يكرر", parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=echo_handler,
        ))
        assert "echo" in reg.list_tools()

    @pytest.mark.asyncio
    async def test_validate_missing_required(self):
        from app.tools.registry import RegisteredTool, ToolRegistry

        reg = ToolRegistry()
        reg.register(RegisteredTool(
            name="echo", description="يكرر", parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=echo_handler,
        ))
        result = await reg.execute("echo", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_success(self):
        from app.tools.registry import RegisteredTool, ToolRegistry

        reg = ToolRegistry()
        reg.register(RegisteredTool(
            name="echo", description="يكرر", parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=echo_handler,
        ))
        result = await reg.execute("echo", {"text": "hello"})
        assert result["out"] == "hello"

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self):
        from app.tools.registry import ToolRegistry

        reg = ToolRegistry()
        with pytest.raises(KeyError):
            await reg.execute("unknown", {})
