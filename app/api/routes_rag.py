"""
Routes: RAG — الاسترجاع والبحث.

POST /rag/search   → بحث متجهي/هجين
POST /rag/hybrid   → بحث هجين صريح
POST /rag/rerank   → إعادة ترتيب
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.rag.retriever import DocumentRetriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


class SearchRequest(BaseModel):
    query: str
    source_id: str = ""
    top_k: int = 10
    mode: str = "hybrid"


class RerankRequest(BaseModel):
    query: str
    results: list


@router.post("/search")
async def search(request: SearchRequest) -> dict:
    """بحث متجهي في الذاكرة المتجهية (مع hybrid fallback)."""
    try:
        retriever = DocumentRetriever()
        results = await retriever.retrieve(
            query=request.query,
            source_id=request.source_id,
            top_k=request.top_k,
        )
        return {"results": results, "count": len(results)}
    except Exception as exc:
        logger.exception("فشل البحث")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/hybrid")
async def hybrid_search(request: SearchRequest) -> dict:
    from app.rag.hybrid_search import HybridSearcher

    try:
        searcher = HybridSearcher()
        results = await searcher.search(
            query=request.query,
            source_id=request.source_id,
            top_k=request.top_k,
        )
        return {"results": results, "count": len(results)}
    except Exception as exc:
        logger.exception("فشل البحث الهجين")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rerank")
async def rerank(request: RerankRequest) -> dict:
    try:
        from app.rag.reranker import CrossEncoderReranker

        settings = get_settings()
        reranker = CrossEncoderReranker()
        results = reranker.rerank(
            query=request.query,
            documents=request.results,
            top_k=min(len(request.results), settings.rag_rerank_top_k),
        )
        return {"results": results, "count": len(results)}
    except RuntimeError as exc:
        return {
            "results": request.results[: get_settings().rag_rerank_top_k],
            "note": f"reranker غير متاح: {exc}",
        }
