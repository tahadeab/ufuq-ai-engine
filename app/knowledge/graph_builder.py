"""
Knowledge Graph Builder — بناء الرسم المعرفي من المفاهيم والعلاقات.

المبدأ: بناء + تحقق خوارزمي + ترتيب طوبولوجي في عملية واحدة.
الرسم لا يُعتبر صالحاً إلا بعد:
1. تحقق العلاقات (النوع مسموح، الثقة فوق الحد، الأجزاء موجودة).
2. كشف الدورات الخوارزمي.
3. الترتيب الطوبولوجي (Kahn).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings
from app.schemas.concepts import Concept, Relationship, RELATION_TYPES
from app.schemas.graph import GraphEdge, GraphMetadata, GraphNode, KnowledgeGraph

logger = logging.getLogger(__name__)


# العلاقات الموجهة التي تُستخدم في الرسم الموجه (للترتيب الطوبولوجي)
DIRECTED_RELATIONS = {"prerequisite_of", "depends_on", "part_of", "type_of"}


class GraphBuilder:
    """يحول قائمة مفاهيم + علاقات إلى KnowledgeGraph صالح ومرتب."""

    def __init__(self):
        settings = get_settings()
        self.min_confidence = settings.min_relationship_confidence

    def build(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
        source_id: str,
        graph_id: Optional[str] = None,
    ) -> Tuple[KnowledgeGraph, List[str]]:
        """
        Returns:
            (graph, issues) حيث issues قائمة مشاكل (تكرارات، ثقة منخفضة، ...)
        """
        issues: List[str] = []
        concept_ids = {c.id for c in concepts}
        concept_map = {c.id: c for c in concepts}

        # ── 1. بناء العقد ──────────────────────────────────
        nodes = [
            GraphNode(
                id=c.id,
                name=c.name,
                type=c.type,
                definition=c.definition,
                metadata={
                    "source_chunk_ids": c.source_chunk_ids,
                    "confidence": c.confidence,
                },
            )
            for c in concepts
        ]

        # ── 2. فلترة وبناء الحواف مع التحقق ────────────────
        edges: List[GraphEdge] = []
        seen_pairs: set = set()
        for rel in relationships:
            if rel.relation not in RELATION_TYPES:
                issues.append(
                    f"علاقة مرفوضة بنوع غير مسموح: {rel.relation} "
                    f"({rel.source_concept_id} → {rel.target_concept_id})"
                )
                continue
            if rel.source_concept_id not in concept_ids:
                issues.append(
                    f"علاقة بمصدر غير موجود: {rel.source_concept_id} → {rel.target_concept_id}"
                )
                continue
            if rel.target_concept_id not in concept_ids:
                issues.append(
                    f"علاقة بهدف غير موجود: {rel.source_concept_id} → {rel.target_concept_id}"
                )
                continue
            if rel.confidence < self.min_confidence:
                issues.append(
                    f"علاقة ثقة منخفضة ({rel.confidence:.2f}<{self.min_confidence}): "
                    f"{concept_map[rel.source_concept_id].name} → "
                    f"{concept_map[rel.target_concept_id].name}"
                )
                continue

            pair = (rel.source_concept_id, rel.relation, rel.target_concept_id)
            if pair in seen_pairs:
                issues.append(f"علاقة مكررة: {pair}")
                continue
            seen_pairs.add(pair)

            edges.append(
                GraphEdge(
                    source=rel.source_concept_id,
                    target=rel.target_concept_id,
                    relation=rel.relation,
                    confidence=rel.confidence,
                    evidence=rel.evidence_chunk_ids,
                )
            )

        # ── 3. كشف الدورات الخوارزمي ───────────────────────
        adjacency: Dict[str, List[str]] = {n.id: [] for n in nodes}
        for edge in edges:
            if edge.relation in DIRECTED_RELATIONS:
                adjacency.setdefault(edge.source, [])
                adjacency.setdefault(edge.target, [])
                adjacency[edge.source].append(edge.target)

        from app.algorithms.cycle_detection import detect_cycles

        has_cycle, cycles = detect_cycles(adjacency)
        if has_cycle:
            for cycle in cycles:
                names = " → ".join(concept_map.get(n, n).name for n in cycle)
                issues.append(f"دورة متطلبات مكتشفة: {names}")

        # ── 4. الترتيب الطوبولوجي ──────────────────────────
        from app.algorithms.topological_sort import topological_sort_kahn

        node_ids = [n.id for n in nodes]
        topo_order, is_acyclic = topological_sort_kahn(node_ids, adjacency)
        if not is_acyclic:
            # عقد متبقية في دورات: ألحقها في نهاية الترتيب
            remaining = [n for n in node_ids if n not in topo_order]
            issues.append(
                f"عقد متبقية في دورات ({len(remaining)}) — ألحقت في نهاية الترتيب"
            )
            topo_order = topo_order + remaining

        metadata = GraphMetadata(
            algorithm_validated=True,
            cycles_detected=len(cycles),
            cycles=cycles,
            topological_order=topo_order,
            node_count=len(nodes),
            edge_count=len(edges),
        )

        graph = KnowledgeGraph(
            graph_id=graph_id or f"g-{source_id}",
            source_id=source_id,
            nodes=nodes,
            edges=edges,
            metadata=metadata,
        )

        logger.info(
            "الرسم المعرفي: %d عقدة، %d حافة، %d دورة، %d مشاكل تحقق",
            len(nodes), len(edges), len(cycles), len(issues),
        )
        return graph, issues

    @staticmethod
    def adjacency_from_edges(
        edges: List[Dict[str, Any]], node_ids: List[str]
    ) -> Dict[str, List[str]]:
        """بناء adjacency من تمثيل JSON (للاستخدام العام)."""
        adj: Dict[str, List[str]] = {n: [] for n in node_ids}
        for edge in edges:
            if edge.get("relation") in DIRECTED_RELATIONS:
                src, tgt = edge.get("source"), edge.get("target")
                if src in adj and tgt in adj:
                    adj[src].append(tgt)
        return adj
