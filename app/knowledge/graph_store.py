"""
Graph Store — repository للرسم المعرفي.

المبدأ: تنفيذ PostgreSQL أولاً (MVP)، وinterface مجردة
تسمح بالانتقال إلى Neo4j مستقبلاً بتغيير factory فقط.
كل الوصول للـDB عبر هذه الطبقة — لا SQL في الـAgent أو Tools.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.schemas.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class GraphRepository(ABC):
    @abstractmethod
    async def save_graph(self, graph: KnowledgeGraph) -> None: ...

    @abstractmethod
    async def get_graph(self, source_id: str) -> Optional[KnowledgeGraph]: ...

    @abstractmethod
    async def delete_graph(self, source_id: str) -> None: ...

    @abstractmethod
    async def get_concepts(self, source_id: str) -> List[Dict]: ...


class PostgresGraphRepository(GraphRepository):
    """تنفيذ PostgreSQL (pgvector) — جداول concepts + relationships."""

    def __init__(self):
        self._engine = None
        self._schema_synced = False

    @property
    def engine(self):
        if self._engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine

            from app.config import get_settings

            self._engine = create_async_engine(get_settings().database_url)
        return self._engine

    async def ensure_schema(self) -> None:
        if self._schema_synced:
            return
        try:
            from sqlalchemy import text

            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS concepts (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            definition TEXT,
                            source_id TEXT NOT NULL,
                            confidence REAL,
                            metadata JSONB DEFAULT '{}'::jsonb
                        );
                        CREATE TABLE IF NOT EXISTS relationships (
                            id TEXT PRIMARY KEY,
                            source_concept_id TEXT NOT NULL REFERENCES concepts(id),
                            relation TEXT NOT NULL,
                            target_concept_id TEXT NOT NULL REFERENCES concepts(id),
                            evidence_chunk_ids JSONB DEFAULT '[]'::jsonb,
                            confidence REAL,
                            UNIQUE (source_concept_id, relation, target_concept_id)
                        );
                        """
                    )
                )
            self._schema_synced = True
            logger.info("schema رسم المعرفة جاهز")
        except Exception:
            logger.exception("فشل إنشاء schema — نتابع في وضع الذاكرة")

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        await self.ensure_schema()
        try:
            from sqlalchemy import text

            async with self.engine.begin() as conn:
                await conn.execute(text("DELETE FROM relationships WHERE source_concept_id IN (SELECT id FROM concepts WHERE source_id = :sid)"), {"sid": graph.source_id})
                await conn.execute(text("DELETE FROM concepts WHERE source_id = :sid"), {"sid": graph.source_id})

                for node in graph.nodes:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO concepts (id, name, type, definition, source_id, confidence, metadata)
                            VALUES (:id, :name, :type, :definition, :source_id, :confidence, :metadata::jsonb)
                            """
                        ),
                        {
                            "id": node.id,
                            "name": node.name,
                            "type": node.type,
                            "definition": node.definition,
                            "source_id": graph.source_id,
                            "confidence": node.metadata.get("confidence", 0.8),
                            "metadata": __import__("json").dumps(node.metadata, ensure_ascii=False),
                        },
                    )
                for i, edge in enumerate(graph.edges):
                    await conn.execute(
                        text(
                            """
                            INSERT INTO relationships (id, source_concept_id, relation, target_concept_id, evidence_chunk_ids, confidence)
                            VALUES (:id, :src, :rel, :tgt, :ev::jsonb, :conf)
                            """
                        ),
                        {
                            "id": f"r-{graph.graph_id}-{i}",
                            "src": edge.source,
                            "rel": edge.relation,
                            "tgt": edge.target,
                            "ev": __import__("json").dumps(edge.evidence, ensure_ascii=False),
                            "conf": edge.confidence,
                        },
                    )
        except Exception:
            logger.exception("فشل حفظ الرسم في Postgres — نتابع دون تخزين دائم")

    async def get_graph(self, source_id: str) -> Optional[KnowledgeGraph]:
        await self.ensure_schema()
        try:
            from sqlalchemy import text

            async with self.engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text("SELECT id, name, type, definition, metadata FROM concepts WHERE source_id = :sid"),
                        {"sid": source_id},
                    )
                ).mappings().all()

                edges = (
                    await conn.execute(
                        text(
                            """
                            SELECT source_concept_id, relation, target_concept_id, evidence_chunk_ids, confidence
                            FROM relationships
                            WHERE source_concept_id IN (SELECT id FROM concepts WHERE source_id = :sid)
                            """
                        ),
                        {"sid": source_id},
                    )
                ).mappings().all()
        except Exception:
            logger.exception("فشل قراءة الرسم")
            return None

        from app.schemas.graph import GraphEdge, GraphMetadata, GraphNode

        nodes = [
            GraphNode(id=r["id"], name=r["name"], type=r["type"],
                      definition=r["definition"], metadata=r["metadata"] or {})
            for r in rows
        ]
        edge_list = [
            GraphEdge(source=e["source_concept_id"], target=e["target_concept_id"],
                      relation=e["relation"], confidence=e["confidence"] or 0.8,
                      evidence=e["evidence_chunk_ids"] or [])
            for e in edges
        ]
        return KnowledgeGraph(
            graph_id=f"g-{source_id}",
            source_id=source_id,
            nodes=nodes,
            edges=edge_list,
            metadata=GraphMetadata(node_count=len(nodes), edge_count=len(edge_list)),
        )

    async def delete_graph(self, source_id: str) -> None:
        try:
            from sqlalchemy import text

            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        DELETE FROM relationships WHERE source_concept_id IN
                        (SELECT id FROM concepts WHERE source_id = :sid)
                        """
                    ),
                    {"sid": source_id},
                )
                await conn.execute(
                    text("DELETE FROM concepts WHERE source_id = :sid"),
                    {"sid": source_id},
                )
        except Exception:
            logger.exception("فشل حذف الرسم")

    async def get_concepts(self, source_id: str) -> List[Dict]:
        await self.ensure_schema()
        try:
            from sqlalchemy import text

            async with self.engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text("SELECT id, name, type, definition, confidence, metadata FROM concepts WHERE source_id = :sid"),
                        {"sid": source_id},
                    )
                ).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            return []


class InMemoryGraphRepository(GraphRepository):
    """repository للذاكرة — للاختبارات وعند غياب Postgres."""

    def __init__(self):
        self._graphs: Dict[str, KnowledgeGraph] = {}

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        self._graphs[graph.source_id] = graph

    async def get_graph(self, source_id: str) -> Optional[KnowledgeGraph]:
        return self._graphs.get(source_id)

    async def delete_graph(self, source_id: str) -> None:
        self._graphs.pop(source_id, None)

    async def get_concepts(self, source_id: str) -> List[Dict]:
        graph = self._graphs.get(source_id)
        if not graph:
            return []
        return [
            {"id": n.id, "name": n.name, "type": n.type,
             "definition": n.definition, "metadata": n.metadata}
            for n in graph.nodes
        ]


_store: Optional[GraphRepository] = None


def get_graph_store() -> GraphRepository:
    global _store
    if _store is None:
        try:
            _store = PostgresGraphRepository()
        except Exception:
            _store = InMemoryGraphRepository()
    return _store


def set_graph_store(store: GraphRepository) -> None:
    """للحقن في الاختبارات."""
    global _store
    _store = store
