"""
Embedding Service — خدمة تضمين GPU-aware.

المبدأ (من الاستراتيجية): النماذج لا تبقى محمَّلة دائماً على جهاز 6GB VRAM.
هذه الخدمة تعرض acquire/release حتى يمكن تفريغ النموذج بعد انتهاء مرحلة
التضمين وإخلاء الذاكرة قبل تحميل LLM.
"""

from __future__ import annotations

import gc
import logging
import threading
from typing import List, Optional

import numpy as np

from app.config import get_settings
from app.embeddings.model import BGE_M3_Embedding, EmbeddingModel

logger = logging.getLogger(__name__)


class EmbeddingService:
    """_singleton lazy-loading مع إدارة ذاكرة صريحة."""

    def __init__(self):
        self._model: Optional[EmbeddingModel] = None
        self._lock = threading.Lock()

    def acquire(self) -> EmbeddingModel:
        with self._lock:
            if self._model is None:
                self._model = BGE_M3_Embedding()
            return self._model

    def release(self) -> None:
        """تفريغ النموذج من الذاكرة (مهم على VRAM محدود)."""
        with self._lock:
            self._model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("تم تفريغ CUDA cache بعد انتهاء التضمين")
        except ImportError:
            pass

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        model = self.acquire()
        try:
            return model.embed(texts)
        finally:
            # لا نفرّغ تلقائياً هنا — الخدمة تقرر متى
            pass


# singleton على مستوى التطبيق
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
