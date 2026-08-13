"""
Semantic Chunking — تقسيم المحتوى مع الحفاظ على البنية.

المبدأ (من وثيقة المشروع): لا نقسم كل N كلمة بشكل أعمى.
نقسم على حدود العناوين (Heading-aware) مع دمج/تقسيم حسب حجم المقطع،
ونحتفظ دائماً بـ chapter/section/subsection/page/topic لكل chunk
لأن الهدف النهائي هو Knowledge Map يشير كل عقد فيه لموقعه في المستند.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import get_settings
from app.ingestion.docling_parser import HeadingBlock, ParsedDocument

logger = __import__("logging").getLogger(__name__)


@dataclass
class Chunk:
    """مقطع من المستند — الوحدة الأساسية لكل العمليات اللاحقة."""

    chunk_id: str
    source_id: str
    text: str
    page: int
    chapter: str = ""
    section: str = ""
    subsection: str = ""
    topic: str = ""
    heading_path: str = ""        # "الفصل 2 > القسم 1.3"
    word_count: int = 0
    metadata: Dict = field(default_factory=dict)

    def to_payload(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "text": self.text,
            "page": self.page,
            "chapter": self.chapter,
            "section": self.section,
            "subsection": self.subsection,
            "topic": self.topic,
            "heading_path": self.heading_path,
            "word_count": self.word_count,
            **self.metadata,
        }


# أنماط عناوين Markdown الشائعة في النصوص المستخرجة
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")


def _is_heading(line: str) -> Optional[int]:
    m = _HEADING_RE.match(line.strip())
    if m:
        return len(m.group(1))
    return None


class SemanticChunker:
    """
    تقسيم يحترم العناوين:
    1. يبدأ chunk جديد عند كل عنوان رئيسي (level 1–2).
    2. العناوين الفرعية تُدرج داخل chunk الأب.
    3. إذا تجاوز chunk الحد الأقصى للكلمات يُقسم إلى مقاطع فرعية
       عند أقرب نهاية فقرة (لا يقطع كلمة في المنتصف).
    """

    def __init__(self):
        settings = get_settings()
        self.target_words = settings.chunk_target_words
        self.overlap_words = settings.chunk_overlap_words
        self.max_words = settings.max_chunk_words

    def chunk_document(
        self, document: ParsedDocument, source_id: str
    ) -> List[Chunk]:
        chunks: List[Chunk] = []
        current_segments: List[str] = []
        current_size = 0
        current_chapter = ""
        current_section = ""
        current_subsection = ""
        current_page = 1
        heading_stack: List[str] = []

        def flush(topic: str = "") -> None:
            nonlocal current_segments, current_size
            if not current_segments:
                return
            text = "\n".join(current_segments).strip()
            if not text:
                current_segments, current_size = [], 0
                return
            chunks.append(
                Chunk(
                    chunk_id=f"chk-{source_id}-{uuid.uuid4().hex[:8]}",
                    source_id=source_id,
                    text=text,
                    page=current_page,
                    chapter=current_chapter,
                    section=current_section,
                    subsection=current_subsection,
                    topic=topic or current_section or current_chapter,
                    heading_path=" > ".join(heading_stack),
                    word_count=len(text.split()),
                )
            )
            current_segments, current_size = [], 0

        for page in document.pages:
            current_page = page.page_number
            lines = page.text.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                level = _is_heading(line)
                if level is not None:
                    # عنوان جديد — أغلق المقطع الحالي إذا كان كبيراً
                    title_text = _HEADING_RE.match(line).group(2).strip()
                    if level == 1:
                        flush()
                        current_chapter = title_text
                        current_section = ""
                        current_subsection = ""
                        heading_stack = [title_text]
                    elif level == 2:
                        flush()
                        current_section = title_text
                        current_subsection = ""
                        heading_stack = heading_stack[:1] + [title_text]
                    else:
                        current_subsection = title_text
                        heading_stack = (heading_stack[:2] + [title_text])[:3]
                    current_segments.append(line)
                    current_size += len(line.split())
                    continue

                words = len(line.split())
                # قسم كبير جداً؟ أغلق وافتح جديداً
                if current_size + words > self.max_words:
                    flush()
                current_segments.append(line)
                current_size += words

                # وصلنا للحجم المستهدف مع نهاية فقرة؟ أغلق
                if current_size >= self.target_words:
                    flush()

        flush()
        return chunks

    def split_oversized(self, chunk: Chunk) -> List[Chunk]:
        """تقسيم مقطع تجاوز الحد الأقصى عند أقرب نهاية فقرة."""
        words = chunk.text.split()
        if len(words) <= self.max_words:
            return [chunk]

        result: List[Chunk] = []
        idx = 0
        part = 1
        while idx < len(words):
            segment = words[idx : idx + self.max_words]
            # لا نقطع جملة: ابحث عن نهاية فقرة/نقطة قريبة من النهاية
            end = len(segment)
            text_joined = " ".join(segment)
            last_para = text_joined.rfind("\n\n")
            last_dot = text_joined.rfind(". ")
            split_at = max(last_para, last_dot)
            if 0.5 * self.max_words < split_at < self.max_words - 20:
                split_words = len(text_joined[:split_at].split())
                segment = words[idx : idx + split_words]

            result.append(
                Chunk(
                    chunk_id=f"{chunk.chunk_id}-p{part}",
                    source_id=chunk.source_id,
                    text=" ".join(segment),
                    page=chunk.page,
                    chapter=chunk.chapter,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    topic=chunk.topic,
                    heading_path=f"{chunk.heading_path} (جزء {part})",
                    word_count=len(segment),
                )
            )
            idx += len(segment)
            part += 1
        return result
