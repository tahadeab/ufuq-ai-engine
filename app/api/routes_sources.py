"""
Routes: Sources — إدارة المستندات وIngestion.

POST /sources/upload   → رفع مستند جديد (multipart)
POST /sources/url      → معالجة رابط/ملف عن بعد
GET  /sources/{id}     → معلومات المصدر
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.ingestion.chunker import SemanticChunker
from app.ingestion.docling_parser import DoclingParser, ParsedDocument
from app.tools.document_tools import register_parsed
from app.vectorstore.qdrant_store import get_chunk_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

_parser = DoclingParser()
_chunker = SemanticChunker()
_sources_meta: dict = {}


@router.post("/upload")
async def upload_source(file: UploadFile = File(...)) -> dict:
    """رفع مستند جديد وتخزينه محلياً، ثم تخليطه ودمجه في الذاكرة المتجهية."""
    settings = get_settings()
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".pdf", ".docx", ".doc", ".md", ".txt", ".pptx", ".html", ".htm"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"نوع ملف غير مدعوم: {ext}")

    source_id = f"src-{uuid.uuid4().hex[:12]}"
    save_dir = os.path.join(settings.storage_dir, "uploads")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{source_id}{ext}")

    with open(save_path, "wb") as fh:
        fh.write(await file.read())

    try:
        parsed = await _parser.parse(save_path)
        chunks = _chunker.chunk_document(parsed, source_id)

        chunk_payloads = [
            c.to_payload() if hasattr(c, "to_payload") else dict(c)
            for c in chunks
        ]
        await get_chunk_store().ensure_collection()
        from app.embeddings.service import get_embedding_service

        texts = [p.get("text", "") for p in chunk_payloads]
        vectors = get_embedding_service().embed_texts(texts)
        await get_chunk_store().add_chunks(source_id, chunk_payloads, vectors)
        register_parsed(source_id, parsed, chunks)

        _sources_meta[source_id] = {
            "source_id": source_id,
            "filename": file.filename,
            "file_type": ext.lstrip("."),
            "title": parsed.title,
            "chunk_count": len(chunks),
            "word_count": parsed.word_count,
            "page_count": len(parsed.pages),
        }
        return {
            "source_id": source_id,
            "status": "indexed",
            "title": parsed.title,
            "chunk_count": len(chunks),
        }
    except Exception as exc:
        logger.exception("فشل معالجة الملف %s", file.filename)
        raise HTTPException(status_code=500, detail=f"فشل معالجة الملف: {exc}")


@router.post("/url")
async def add_source_url(payload: dict) -> dict:
    """إضافة مصدر عبر رابط (PDF عام أو صفحة ويب)."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="url مطلوب")
    source_id = f"src-{uuid.uuid4().hex[:12]}"
    try:
        parsed = await _parser.parse(url)
        chunks = _chunker.chunk_document(parsed, source_id)
        chunk_payloads = [
            c.to_payload() if hasattr(c, "to_payload") else dict(c)
            for c in chunks
        ]
        await get_chunk_store().ensure_collection()
        from app.embeddings.service import get_embedding_service

        texts = [p.get("text", "") for p in chunk_payloads]
        vectors = get_embedding_service().embed_texts(texts)
        await get_chunk_store().add_chunks(source_id, chunk_payloads, vectors)
        register_parsed(source_id, parsed, chunks)
        _sources_meta[source_id] = {
            "source_id": source_id,
            "url": url,
            "file_type": "url",
            "title": parsed.title,
            "chunk_count": len(chunks),
        }
        return {
            "source_id": source_id,
            "status": "indexed",
            "title": parsed.title,
            "chunk_count": len(chunks),
        }
    except Exception as exc:
        logger.exception("فشل معالجة الرابط %s", url)
        raise HTTPException(status_code=500, detail=f"فشل معالجة الرابط: {exc}")


@router.get("/{source_id}")
async def get_source_meta(source_id: str) -> dict:
    meta = _sources_meta.get(source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="المصدر غير موجود")
    return meta
