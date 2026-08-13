"""
Hybrid RAG — البحث الهجين.

```text
         الاستعلام
        ┌────┴────┐
        ▼         ▼
  Vector      Keyword
  Search      (BM25)
        └────┬────┘
             ▼
      Reciprocal Rank Fusion (RRF)
             ▼
        Reranker (اختياري)
             ▼
    Top-k Chunks + Scores
```

المبدأ: Vector search يلتقط التشابه المعنوي، Keyword يلتقط
المطابقات الحرفية الدقيقة (أسماء مفاهيم، مصطلحات)،
وRRF يدمجهما دون الحاجة لمعايرة درجات.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    weights: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    RRF: score(d) = Σ weight_i / (k + rank_i(d))
    k=60 هو القيمة القياسية الموصى بها في الأدبيات.
    """
    scores: Dict[str, float] = defaultdict(float)
    seen: Dict[str, Dict[str, Any]] = {}

    for i, ranked_list in enumerate(ranked_lists):
        weight = weights[i] if weights and i < len(weights) else 1.0
        for rank, item in enumerate(ranked_list, start=1):
            chunk_id = item.get("chunk_id") or item.get("id") or str(item)
            scores[chunk_id] += weight / (k + rank)
            if chunk_id not in seen:
                seen[chunk_id] = item

    merged = [
        {**seen[cid], "hybrid_score": round(scores[cid], 6)}
        for cid in sorted(scores, key=scores.get, reverse=True)
    ]
    return merged


def keyword_search_local(
    chunks: List[Dict[str, Any]], query: str, top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    بحث كلمات مفتاحية بسيط (TF-based) يعمل دون bm25 server.
    عندما يعمل Qdrant بـsparse vectors، يُستبدل بـBM25 الرسمي.
    """
    query_terms = set(_tokenize(query))
    if not query_terms:
        return []

    scored = []
    for chunk in chunks:
        text = chunk.get("text", "")
        tokens = _tokenize(text)
        if not tokens:
            continue
        matches = len(query_terms & set(tokens))
        if matches == 0:
            continue
        tf = matches / max(len(tokens), 1)
        scored.append({**chunk, "keyword_score": round(tf, 6)})

    scored.sort(key=lambda x: x["keyword_score"], reverse=True)
    return scored[:top_k]


def _tokenize(text: str) -> List[str]:
    """تقسيم بسيط يدعم العربي والإنجليزي (بدون stemming في MVP)."""
    import re
    import unicodedata

    # إزالة التشكيل العربي
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    words = re.findall(r"[\w\u0600-\u06FF]+", text.lower())
    return [w for w in words if len(w) > 1]


class HybridSearcher:
    """يجمع vector search + keyword + RRF + reranking."""

    def __init__(self, vector_store, embedding_service):
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    async def search(
        self,
        query: str,
        source_id: Optional[str] = None,
        all_chunks: Optional[List[Dict[str, Any]]] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        all_chunks تُمرَّر للبحث المحلي بالكلمات المفتاحية
        (في MVP نخزّن chunks محلياً في Job context أيضاً).
        """
        settings = get_settings()
        top_k = top_k or settings.rag_top_k

        # 1) vector search
        query_vec = self.embedding_service.embed_texts([query])[0]
        vector_results = await self.vector_store.search_similar(
            source_id=source_id, vector=query_vec, top_k=top_k * 2
        )

        # 2) keyword search (محلي إن لم تتوفر chunks)
        keyword_results: List[Dict[str, Any]] = []
        if all_chunks:
            filtered = (
                [c for c in all_chunks if c.get("source_id") == source_id]
                if source_id
                else all_chunks
            )
            keyword_results = keyword_search_local(filtered, query, top_k=top_k * 2)

        # 3) fusion
        fused = reciprocal_rank_fusion(
            ranked_lists=[vector_results, keyword_results],
            weights=[2.0, 1.0],  # vector أثقل قليلاً (معايرة أولى)
        )
        return fused[:top_k]
