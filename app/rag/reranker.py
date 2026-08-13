"""
Reranker — إعادة ترتيب نتائج الاسترجاع.

المبدأ: reranker حتمي-تقريبي (cross-encoder) قبل التوليد،
لا LLM. إذا تعذر تحميل النموذج (VRAM محدود) يسقط النظام
بشكل آمن لـhybrid score دون توقف.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """bge-reranker-v2-m3 عبر sentence-transformers.CrossEncoder."""

    def __init__(self, model_name: str | None = None):
        from app.config import get_settings

        settings = get_settings()
        self.model_name = model_name or settings.reranker_model
        self._model = None

        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            logger.info("Reranker محمَّل: %s", self.model_name)
        except Exception as exc:
            raise RuntimeError(f"فشل تحميل reranker: {exc}") from exc

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if not self._model or not documents:
            return documents

        pairs = [(query, doc.get("text", "")) for doc in documents]
        scores = self._model.predict(pairs).tolist()

        ranked = sorted(
            zip(documents, scores), key=lambda x: x[1], reverse=True
        )
        return [
            {**doc, "rerank_score": round(float(score), 6)}
            for doc, score in ranked[:top_k]
        ]
