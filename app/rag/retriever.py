"""
Retriever — واجهة الاسترجاع القياسية المستخدمة من كل أدوات الـAgent.

يجمّع: hybrid search → reranking (اختياري) → citation enrichment.
```text
query ──▶ HybridSearcher ──▶ [reranker] ──▶ cited chunks
```
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.embeddings.service import get_embedding_service
from app.rag.hybrid_search import HybridSearcher
from app.vectorstore.qdrant_store import get_chunk_store

logger = logging.getLogger(__name__)


class DocumentRetriever:
    """نقطة الدخول الوحيدة للاسترجاع من بقية النظام."""

    def __init__(self):
        settings = get_settings()
        self.vector_store = get_chunk_store()
        self.embedding_service = get_embedding_service()
        self.hybrid = HybridSearcher(self.vector_store, self.embedding_service)
        self.top_k = settings.rag_top_k
        self.rerank_top_k = settings.rag_rerank_top_k
        self.reranker_enabled = settings.rag_reranker_enabled

        self._reranker = None
        if self.reranker_enabled:
            try:
                from app.rag.reranker import CrossEncoderReranker

                self._reranker = CrossEncoderReranker()
            except RuntimeError as exc:
                logger.warning("Reranker غير متاح: %s — سيُستخدم scoring بديل", exc)
                self.reranker_enabled = False

    async def retrieve(
        self,
        query: str,
        source_id: Optional[str] = None,
        all_chunks: Optional[List[Dict[str, Any]]] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        top_k = top_k or self.top_k

        results = await self.hybrid.search(
            query=query,
            source_id=source_id,
            all_chunks=all_chunks,
            top_k=top_k * 3 if self.reranker_enabled else top_k,
        )

        if self.reranker_enabled and self._reranker and results:
            results = self._reranker.rerank(
                query=query, documents=results, top_k=min(self.rerank_top_k, len(results))
            )
        else:
            results = results[:top_k]

        return self._add_citations(results)

    @staticmethod
    def _add_citations(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for r in results:
            item = dict(r)
            item["citation"] = {
                "chunk_id": r.get("chunk_id"),
                "source_id": r.get("source_id"),
                "page": r.get("page"),
                "heading_path": r.get("heading_path"),
            }
            out.append(item)
        return out
