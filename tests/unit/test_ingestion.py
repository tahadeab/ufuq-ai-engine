"""
اختبارات Ingestion — Semantic Chunker.

الواجهة الفعلية: chunk_document(document: ParsedDocument, source_id) → List[Chunk]
"""

import pytest

from app.ingestion.chunker import Chunk, SemanticChunker
from app.ingestion.docling_parser import PageBlock, ParsedDocument


def make_document(pages: list, title: str = "مستند تجريبي") -> ParsedDocument:
    page_objects = [
        PageBlock(page_number=i + 1, text=text) for i, text in enumerate(pages)
    ]
    return ParsedDocument(
        title=title,
        file_path="/tmp/test.md",
        file_type="md",
        pages=page_objects,
        word_count=sum(len(p.split()) for p in pages),
    )


class TestSemanticChunker:
    def setup_method(self):
        self.chunker = SemanticChunker()

    def test_splits_on_headings(self):
        """عناوين H1/H2 تبدأ chunks جديدة منفصلة."""
        pages = [
            "\n".join(["نص. "] * 50),
            "\n".join(
                [
                    "# الفصل الأول",
                    "نص الفصل الأول. " * 30,
                    "## القسم أ",
                    "نص القسم. " * 40,
                ]
            ),
        ]
        doc = make_document(pages)
        chunks = self.chunker.chunk_document(doc, source_id="s-1")
        assert len(chunks) >= 2
        # كل chunk يحمل source_id
        assert all(c.source_id == "s-1" for c in chunks)
        assert all(c.chunk_id.startswith("chk-s-1") for c in chunks)

    def test_heading_path_captured(self):
        pages = ["# الباب الأول\nنص طويل. " * 20, "## القسم الأول\nنص القسم. " * 30]
        chunks = self.chunker.chunk_document(make_document(pages), source_id="s-1")
        paths = [c.heading_path for c in chunks if c.heading_path]
        assert any("الباب الأول" in p for p in paths)

    def test_oversized_chunk_split(self):
        """split_oversized يقسم المقاطع الكبيرة دون قطع كلمات."""
        chunk = Chunk(
            chunk_id="chk-big", source_id="s-1", text="كلمة. " * 5000,
            page=1, chapter="", section="", subsection="", topic="",
            heading_path="", word_count=5000,
        )
        parts = self.chunker.split_oversized(chunk)
        assert len(parts) > 1
        # النص الكامل محفوظ
        assert sum(p.word_count for p in parts) >= chunk.word_count
        # لا مقطع يتجاوز الحد
        assert all(p.word_count <= self.chunker.max_words for p in parts)

    def test_no_chunks_for_empty(self):
        doc = make_document([""])
        assert self.chunker.chunk_document(doc, source_id="s-1") == []

    def test_metadata_fields(self):
        doc = make_document(["# باب\n" + "نص. " * 60])
        chunks = self.chunker.chunk_document(doc, source_id="s-1")
        for c in chunks:
            assert c.page >= 1
            payload = c.to_payload()
            assert payload["chunk_id"] == c.chunk_id
            assert payload["word_count"] == c.word_count
