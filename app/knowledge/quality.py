"""Deterministic quality and reliability analysis for grounded learning paths."""
from __future__ import annotations

from typing import Any, Dict, List

from app.knowledge.validator import CitationValidator, verify_source_claim


def analyze_learning_path_quality(
    learning_path: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    graph: Dict[str, Any] | None = None,
    source_id: str = "",
) -> Dict[str, Any]:
    """Return explainable quality metrics; never invents evidence."""
    modules = learning_path.get("modules", []) or []
    chunk_map = {str(c.get("chunk_id")): c for c in chunks if c.get("chunk_id") is not None}
    citation_issues = CitationValidator(chunks, source_id).validate(learning_path) if source_id else []
    objectives_total = 0
    objectives_supported = 0
    unsupported_claims: List[Dict[str, Any]] = []
    cited_modules = 0
    cited_concepts = 0
    concepts_total = 0

    for module in modules:
        citations = module.get("source_citations") or []
        if citations:
            cited_modules += 1
        concepts = module.get("concepts_covered") or []
        concepts_total += len(concepts)
        if citations and concepts:
            cited_concepts += len(concepts)
        for objective in module.get("learning_objectives", []) or []:
            if isinstance(objective, str):
                text, citation_ids = objective, [str(c.get("chunk_id")) for c in citations]
            else:
                text = str(objective.get("text", ""))
                citation_ids = [str(x) for x in (objective.get("citation_ids") or [])]
                if not citation_ids:
                    citation_ids = [str(c.get("chunk_id")) for c in citations]
            objectives_total += 1
            supported = False
            for cid in citation_ids:
                chunk = chunk_map.get(cid)
                if chunk and verify_source_claim(text, str(chunk.get("text") or chunk.get("content") or ""), threshold=0.35):
                    supported = True
                    break
            if supported:
                objectives_supported += 1
            else:
                unsupported_claims.append({"module_id": module.get("module_id"), "claim": text[:300], "citation_ids": citation_ids})

    module_coverage = cited_modules / len(modules) if modules else 0.0
    citation_coverage = objectives_supported / objectives_total if objectives_total else module_coverage
    concept_coverage = cited_concepts / concepts_total if concepts_total else 0.0
    graph_validity = 1.0
    graph_issues: List[str] = []
    if graph is not None:
        nodes = {str(n.get("id")) for n in graph.get("nodes", [])}
        for edge in graph.get("edges", []) or []:
            if str(edge.get("source")) not in nodes or str(edge.get("target")) not in nodes:
                graph_issues.append("edge references a missing node")
        graph_validity = 1.0 if nodes and not graph_issues else 0.0
    citation_score = 0.0 if citation_issues else min(1.0, citation_coverage + (0.1 if modules else 0.0))
    overall = round(max(0.0, min(1.0, 0.35 * citation_score + 0.25 * concept_coverage + 0.25 * graph_validity + 0.15 * module_coverage)), 4)
    return {
        "overall_score": overall,
        "citation_coverage": round(citation_coverage, 4),
        "concept_coverage": round(concept_coverage, 4),
        "graph_validity": round(graph_validity, 4),
        "unsupported_claims": len(unsupported_claims),
        "unsupported_claim_details": unsupported_claims[:50],
        "citation_issues": citation_issues[:50],
        "graph_issues": graph_issues,
        "review_required": bool(citation_issues or unsupported_claims or graph_issues or overall < 0.75),
        "objectives_total": objectives_total,
        "objectives_supported": objectives_supported,
    }
