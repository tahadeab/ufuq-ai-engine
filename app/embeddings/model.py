"""
Embedding Model — واجهة مجردة للتضمين + تنفيذ BGE-M3 محلياً.

المبدأ: BGE-M3 يدعم أكثر من 100 لغة (عربي + إنجليزي)
بتمثيل 1024 بعد وسياق حتى 8192 token — مجاني بالكامل محلياً.
لا نحتاج أي API مدفوع للـembeddings.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingModel(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """نصوص → مصفوفة متجهات (num_texts × dim)."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """أبعاد التمثيل المتجهي."""


class BGE_M3_Embedding(EmbeddingModel):
    """تنفيذ محلي عبر sentence-transformers (أو torch مباشرة)."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        device = device or settings.embedding_device
        if device == "auto":
            device = "cpu"
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                pass
        self.device = device

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name, trust_remote_code=True
            )
            logger.info(
                "BGE-M3 محمَّل على %s — dim=%d", self.device, self.dim
            )
        except ImportError:
            self._model = None
            logger.warning(
                "sentence-transformers غير مثبت. ثبّتها: "
                "pip install 'sentence-transformers'"
            )

    @property
    def dim(self) -> int:
        return get_settings().embedding_dim

    def embed(self, texts: List[str]) -> np.ndarray:
        if self._model is None:
            # وضع CI: تمثيل تكراري بسيط — لا يتطلب أي نماذج
            if get_settings().ci_mode:
                return self._hash_embed(texts)
            raise RuntimeError(
                "نموذج التضمين غير جاهز. ثبّت: pip install 'sentence-transformers' "
                "ثم حمّل النموذج: python -c 'from sentence_transformers import "
                "SentenceTransformer; SentenceTransformer(\"BAAI/bge-m3\")'"
            )
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
        )
        return np.asarray(vectors, dtype=np.float32)

    def _hash_embed(self, texts: List[str]) -> np.ndarray:
        """تمثيل تجريبي (hash-based TF) لوضع CI فقط — لا يستخدم في الإنتاج."""
        dim = self.dim
        out = np.zeros((len(texts), dim), dtype=np.float32)
        for i, text in enumerate(texts):
            positions = np.zeros(dim)
            for tok in text.lower().split():
                positions[abs(hash(tok)) % dim] += 1.0
            norm = float(np.linalg.norm(positions)) or 1.0
            out[i] = positions / norm
        return out
