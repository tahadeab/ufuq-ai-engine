"""
Document Tools — أدوات معالجة المستندات.

get_source / parse_source / get_document_structure / get_chunks
(كما في Tool Registry — القسم 4.1 من وثيقة المشروع)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.ingestion.chunker import SemanticChunker, Chunk
from app.ingestion.docling_parser import ParsedDocument

logger = logging.getLogger(__name__)

# ── مخزن محلي للمستندات المشروحة (الـAgent يعمل عليها) ──────
_parsed_documents: Dict[str, ParsedDocument] = {}
_all_chunks: Dict[str, List[Dict[str, Any]]] = {}


def register_parsed(source_id: str, doc: ParsedDocument, chunks: List[Dict[str, Any]]) -> None:
    """تسجيل مستند مشروح في سياق الـAgent (يُستدعى من pipeline)."""
    _parsed_documents[source_id] = doc
    _all_chunks[source_id] = chunks


async def get_source(source_id: str) -> Dict[str, Any]:
    if source_id not in _parsed_documents:
        raise ValueError(f"المصدر {source_id} غير موجود في السياق")
    doc = _parsed_documents[source_id]
    return {
        "source_id": source_id,
        "title": doc.title,
        "file_type": doc.file_type,
        "path_or_url": doc.file_path,
        "metadata": doc.metadata,
    }


async def parse_source(source_id: str) -> Dict[str, Any]:
    if source_id not in _parsed_documents:
        raise ValueError(f"المصدر {source_id} غير موجود في السياق")
    doc = _parsed_documents[source_id]
    return {
        "document": {
            "title": doc.title,
            "file_type": doc.file_type,
            "page_count": len(doc.pages),
            "word_count": doc.word_count,
            "toc": [
                {"level": h.level, "title": h.text, "page": h.page}
                for h in doc.headings[:100]
            ],
            "metadata": doc.metadata,
        }
    }


async def get_document_structure(source_id: str) -> Dict[str, Any]:
    if source_id not in _parsed_documents:
        raise ValueError(f"المصدر {source_id} غير موجود في السياق")
    doc = _parsed_documents[source_id]

    chapters: List[Dict[str, Any]] = []
    current = None
    for h in sorted(doc.headings, key=lambda x: x.page):
        if h.level == 0:
            current = {"title": h.text, "page": h.page, "sections": []}
            chapters.append(current)
        elif h.level <= 2:
            if current is None:
                current = {"title": "(مقدمة)", "page": h.page, "sections": []}
                chapters.append(current)
            current["sections"].append({"title": h.text, "page": h.page})

    return {"chapters": chapters}


async def get_chunks(
    source_id: str,
    page: int | None = None,
    section: str | None = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    chunks = _all_chunks.get(source_id, [])
    # توحيد الصيغة: Chunk dataclass → dict عبر to_payload()
    dicts = [c.to_payload() if hasattr(c, "to_payload") else dict(c) for c in chunks]
    if page is not None:
        dicts = [c for c in dicts if c.get("page") == page]
    if section:
        dicts = [
            c for c in dicts
            if section.lower() in (c.get("section") or "").lower()
            or section.lower() in (c.get("heading_path") or "").lower()
        ]
    return {"chunks": dicts[:limit], "total": len(dicts)}
