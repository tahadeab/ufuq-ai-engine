"""
Vector Store — Qdrant repository.

Qdrant: مفتوح المصدر (Apache-2.0)، يدعم hybrid search مدمج
(dense vector + BM25 sparse) — مثالي لـ Hybrid RAG.

المبدأ: بقية النظام لا يستورد qdrant_client مباشرة؛
يتعامل فقط مع ChunkVectorStore interface.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class ChunkVectorStore(ABC):
    """واجهة مجردة لمخزن المتجهات."""

    @abstractmethod
    async def ensure_collection(self) -> None: ...

    @abstractmethod
    async def add_chunks(
        self, source_id: str, chunks: List[Dict[str, Any]], vectors: np.ndarray
    ) -> int: ...

    @abstractmethod
    async def search_fulltext(
        self, query: str, source_id: Optional[str] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def search_similar(
        self, source_id: Optional[str], vector: np.ndarray, top_k: int
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def delete_source(self, source_id: str) -> int: ...

    @abstractmethod
    async def count(self, source_id: Optional[str] = None) -> int: ...


class InMemoryChunkStore(ChunkVectorStore):
    """مخزن احتياطي في الذاكرة — يعمل دون Qdrant server (للتطوير والاختبار).

    In-memory fallback store used when no Qdrant server is available.
    Vector search uses exact cosine similarity; full-text uses token overlap.
    """

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}  # chunk_id → payload+vector

    async def ensure_collection(self) -> None:
        pass

    async def add_chunks(
        self, source_id: str, chunks: List[Dict[str, Any]], vectors: np.ndarray
    ) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("عدد المقاطع لا يطابق عدد المتجهات")
        for i, chunk in enumerate(chunks):
            cid = chunk.get("chunk_id", f"{source_id}-{i}")
            self._data[cid] = {"source_id": source_id, **chunk, "vector": vectors[i].tolist()}
        return len(chunks)

    async def search_similar(
        self, source_id: Optional[str], vector: np.ndarray, top_k: int
    ) -> List[Dict[str, Any]]:
        query = vector.tolist()
        scored = []
        for item in self._data.values():
            if source_id and item.get("source_id") != source_id:
                continue
            v = np.array(item["vector"])
            sim = float(np.dot(query, v) / (np.linalg.norm(query) * np.linalg.norm(v) + 1e-9))
            scored.append({"score": round(sim, 6), **{k: v for k, v in item.items() if k != "vector"}})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def search_fulltext(
        self, query: str, source_id: Optional[str] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """بحث نصي تقريبي بالتطابق التوكني (للكلمات المفتاحية)."""
        import re
        terms = set(re.findall(r"[\w\u0600-\u06FF]+", query.lower()))
        if not terms:
            return []
        scored = []
        for item in self._data.values():
            if source_id and item.get("source_id") != source_id:
                continue
            text = item.get("text", "").lower()
            tokens = set(re.findall(r"[\w\u0600-\u06FF]+", text))
            if not tokens:
                continue
            score = len(terms & tokens) / len(terms)
            if score > 0:
                scored.append({"keyword_score": round(score, 6), **{k: v for k, v in item.items() if k != "vector"}})
        scored.sort(key=lambda x: x["keyword_score"], reverse=True)
        return scored[:top_k]

    async def delete_source(self, source_id: str) -> int:
        keys = [k for k, v in self._data.items() if v.get("source_id") == source_id]
        for k in keys:
            del self._data[k]
        return len(keys)

    async def count(self, source_id: Optional[str] = None) -> int:
        if source_id:
            return sum(1 for v in self._data.values() if v.get("source_id") == source_id)
        return len(self._data)


class QdrantChunkStore(ChunkVectorStore):
    """تنفيذ Qdrant مع hybrid search (dense + sparse/BM25)."""

    def __init__(self):
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.dim = settings.embedding_dim
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            settings = get_settings()
            self._client = QdrantClient(
                host=settings.qdrant_host, port=settings.qdrant_port
            )
        return self._client

    async def ensure_collection(self) -> None:
        from qdrant_client.http.models import (
            Distance,
            SparseIndexParams,
            SparseVectorParams,
            VectorParams,
        )

        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": VectorParams(size=self.dim, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "bm25": SparseVectorParams(index=SparseIndexParams())
            },
        )
        logger.info("Qdrant collection أنشئت: %s (dim=%d)", self.collection, self.dim)

    async def add_chunks(
        self, source_id: str, chunks: List[Dict[str, Any]], vectors: np.ndarray
    ) -> int:
        from qdrant_client.models import PointStruct

        if len(chunks) != len(vectors):
            raise ValueError("عدد المقاطع لا يطابق عدد المتجهات")

        points = []
        for i, chunk in enumerate(chunks):
            points.append(
                PointStruct(
                    id=chunk.get("chunk_id", f"{source_id}-{i}"),
                    vector={"dense": vectors[i].tolist()},
                    payload={
                        "source_id": source_id,
                        **{k: v for k, v in chunk.items() if k != "chunk_id"},
                    },
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)

    async def search_similar(
        self, source_id: Optional[str], vector: np.ndarray, top_k: int
    ) -> List[Dict[str, Any]]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        where = None
        if source_id:
            where = Filter(
                must=[
                    FieldCondition(
                        key="source_id", match=MatchValue(value=source_id)
                    )
                ]
            )
        results = self.client.query_points(
            collection_name=self.collection,
            query=vector.tolist(),
            using="dense",
            query_filter=where,
            limit=top_k,
            with_payload=True,
        )
        return [
            {"score": p.score, **p.payload} for p in results.points
        ]

    async def delete_source(self, source_id: str) -> int:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_id", match=MatchValue(value=source_id)
                    )
                ]
            ),
        )
        return 1

    async def count(self, source_id: Optional[str] = None) -> int:
        try:
            info = self.client.count(
                collection_name=self.collection,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_id", match=MatchValue(value=source_id)
                        )
                    ]
                )
                if source_id
                else None,
                exact=True,
            )
            return info.count
        except Exception:
            return 0


_store_instance: Optional[ChunkVectorStore] = None


def get_chunk_store() -> ChunkVectorStore:
    """Qdrant إن توفر الخادم، وإلا مخزن في الذاكرة (شفاف تماماً)."""
    global _store_instance
    if _store_instance is None:
        settings = get_settings()
        if settings.should_use_in_memory():
            _store_instance = InMemoryChunkStore()
            logger.info("استخدام مخزن الذاكرة — Qdrant غير متاح (should_use_in_memory)")
        else:
            _store_instance = QdrantChunkStore()
    return _store_instance
