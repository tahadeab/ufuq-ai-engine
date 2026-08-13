"""
Knowledge Tools — أدوات المعرفة والرسم المعرفي.

extract_concepts / extract_relationships / merge_concepts /
build_graph / validate_graph / detect_cycles / topological_sort
(القسم 4.3 من وثيقة المشروع)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.knowledge.graph_builder import DIRECTED_RELATIONS, GraphBuilder
from app.schemas.concepts import Concept, Relationship

logger = logging.getLogger(__name__)


async def extract_concepts(chunks: list, document_title: str = "") -> Dict[str, Any]:
    from app.knowledge.extractor import KnowledgeExtractor

    chunk_dicts = chunks if isinstance(chunks, list) else chunks.get("chunks", [])
    extractor = KnowledgeExtractor()
    concepts = await extractor.extract_concepts_from_chunks(
        chunks=chunk_dicts, document_title=document_title
    )
    return {
        "concepts": [c.model_dump() for c in concepts],
        "count": len(concepts),
    }


async def extract_relationships(
    concepts: list, chunks: list, document_title: str = ""
) -> Dict[str, Any]:
    from app.knowledge.extractor import KnowledgeExtractor

    concept_objects = [
        Concept(**c) if isinstance(c, dict) else c for c in concepts
    ]
    chunk_dicts = chunks if isinstance(chunks, list) else chunks.get("chunks", [])
    extractor = KnowledgeExtractor()
    rels = await extractor.extract_relationships(
        concepts=concept_objects, chunks=chunk_dicts, document_title=document_title
    )
    return {
        "relationships": [r.model_dump() for r in rels],
        "count": len(rels),
    }


async def merge_concepts(concepts: list) -> Dict[str, Any]:
    """دمج المفاهيم المكررة (case-insensitive على الاسم)."""
    from app.knowledge.validator import check_duplicate_concepts

    merged: Dict[str, Any] = {}
    for c in concepts:
        norm = c.get("name", "").strip().lower()
        if norm in merged:
            merged[norm]["source_chunk_ids"] = sorted(
                set(merged[norm].get("source_chunk_ids", []))
                | set(c.get("source_chunk_ids", []))
            )
            merged[norm]["confidence"] = max(
                merged[norm].get("confidence", 0.8), c.get("confidence", 0.8)
            )
        else:
            merged[norm] = dict(c)
    return {"concepts": list(merged.values()), "count": len(merged)}


async def build_graph(
    concepts: list, relationships: list, source_id: str
) -> Dict[str, Any]:
    from app.knowledge.graph_builder import GraphBuilder

    concept_objects = [
        Concept(**c) if isinstance(c, dict) else c for c in concepts
    ]
    rel_objects = [
        Relationship(**r) if isinstance(r, dict) else r for r in relationships
    ]
    builder = GraphBuilder()
    graph, issues = builder.build(
        concepts=concept_objects, relationships=rel_objects, source_id=source_id
    )
    return {
        "graph": graph.model_dump(),
        "issues": issues,
        "validated": graph.metadata.algorithm_validated,
    }


async def validate_graph(graph: dict) -> Dict[str, Any]:
    from app.knowledge.graph_builder import GraphBuilder
    from app.algorithms.cycle_detection import detect_cycles
    from app.algorithms.topological_sort import topological_sort_kahn

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [n.get("id") for n in nodes]
    adjacency = GraphBuilder.adjacency_from_edges(edges, node_ids)

    has_cycle, cycles = detect_cycles(adjacency)
    order, is_acyclic = topological_sort_kahn(node_ids, adjacency)

    confidence = 1.0 if not has_cycle else max(0.3, 1.0 - len(cycles) * 0.15)
    return {
        "valid": not has_cycle,
        "issues": [] if not has_cycle else [f"دورة: {' → '.join(c)}" for c in cycles],
        "confidence": round(confidence, 3),
        "topological_order": order if is_acyclic else order,
    }


async def detect_cycles(graph: dict) -> Dict[str, Any]:
    from app.knowledge.graph_builder import GraphBuilder
    from app.algorithms.cycle_detection import detect_cycles as _detect

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [n.get("id") for n in nodes]
    adjacency = GraphBuilder.adjacency_from_edges(edges, node_ids)
    has_cycle, cycles = _detect(adjacency)
    return {
        "has_cycle": has_cycle,
        "cycles": cycles,
        "cycle_count": len(cycles),
    }


async def topological_sort(graph: dict) -> Dict[str, Any]:
    from app.knowledge.graph_builder import GraphBuilder
    from app.algorithms.topological_sort import topological_sort_kahn

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [n.get("id") for n in nodes]
    adjacency = GraphBuilder.adjacency_from_edges(edges, node_ids)
    order, is_acyclic = topological_sort_kahn(node_ids, adjacency)
    return {
        "ordered": order,
        "is_acyclic": is_acyclic,
        "node_count": len(order),
    }
