"""
RAG Tools — أدوات الاسترجاع.

semantic_search / hybrid_search / rerank_results
(القسم 4.2 من وثيقة المشروع)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.rag.retriever import DocumentRetriever

logger = logging.getLogger(__name__)


async def semantic_search(source_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
    retriever = DocumentRetriever()
    results = await retriever.retrieve(query=query, source_id=source_id, top_k=top_k)
    return {"results": results, "count": len(results)}


async def keyword_search(source_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
    from app.rag.hybrid_search import keyword_search_local
    from app.tools.document_tools import _all_chunks

    chunks = _all_chunks.get(source_id, [])
    results = keyword_search_local(chunks, query, top_k=top_k)
    return {"results": results, "count": len(results)}


async def hybrid_search(source_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
    return await semantic_search(source_id, query, top_k)


async def rerank_results(query: str, chunks: list) -> Dict[str, Any]:
    from app.config import get_settings

    results: list = chunks if isinstance(chunks, list) else chunks.get("results", [])
    if not results:
        return {"results": [], "count": 0}

    try:
        from app.rag.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query=query, documents=results, top_k=len(results))
        return {"results": reranked, "count": len(reranked)}
    except RuntimeError:
        settings = get_settings()
        return {
            "results": results[: settings.rag_rerank_top_k],
            "count": min(len(results), settings.rag_rerank_top_k),
            "note": "reranker غير متاح — رُجّعت النتائج حسب hybrid score",
        }
