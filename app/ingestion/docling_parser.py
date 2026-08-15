"""
Document Intelligence — طبقة التخليط (Ingestion).

- واجهة مجردة DocumentParser (التقنية قابلة للتبديل).
- التنفيذ الافتراضي: Docling (مفتوح المصدر، MIT، يدعم PDF/DOCX/PPTX/XLSX/HTML/Images).
- الناتج: مستند موحد (نصوص + عناوين + جداول + صور + صفحات + metadata)
  دون أن يقوم LLM بأي دور هنا — أدوات متخصصة فقط.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# نماذج البيانات الموحدة للمستند
# ═══════════════════════════════════════════

@dataclass
class TableBlock:
    caption: str = ""
    rows: List[List[str]] = field(default_factory=list)

    def to_text(self) -> str:
        return " | ".join(" / ".join(cell for cell in row) for row in self.rows)


@dataclass
class PageBlock:
    page_number: int
    text: str
    tables: List[TableBlock] = field(default_factory=list)
    images: int = 0


@dataclass
class HeadingBlock:
    level: int
    text: str
    page: int


@dataclass
class ParsedDocument:
    """المستند الموحد — الناتج الأساسي لطبقة الـIngestion."""

    title: str
    file_path: str
    file_type: str          # pdf | docx | pptx | xlsx | html | image
    pages: List[PageBlock] = field(default_factory=list)
    headings: List[HeadingBlock] = field(default_factory=list)
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


# ═══════════════════════════════════════════
# الواجهة المجردة
# ═══════════════════════════════════════════

class DocumentParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> ParsedDocument:
        """تخليط ملف إلى ParsedDocument موحد."""


# ═══════════════════════════════════════════
# التنفيذ: Docling
# ═══════════════════════════════════════════

class DoclingParser(DocumentParser):
    """تنفيذ Docling مع معالجة أخطاء واضحة وfallback عند تعذر التثبيت."""

    def __init__(self):
        self._docling = None
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401

            self._docling = DocumentConverter()
            logger.info("Docling متاح — Document Intelligence جاهز")
        except ImportError:
            logger.warning(
                "Docling غير مثبت. استبدله بـ pip install 'docling[PDFS]' "
                "أو فعّل الوضع التجريبي للنصوص."
            )

    async def parse(self, file_path: Path) -> ParsedDocument:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"الملف غير موجود: {file_path}")

        file_type = file_path.suffix.lower().lstrip(".")

        # ملفات النصوص تُحلّل مباشرةً دائماً؛ Docling لا يحتاجها وقد
        # يرفضها في بعض الإصدارات رغم أن امتداداتها مسموحة في API.
        if file_type in ("md", "txt", "text"):
            return self._parse_plain_text(file_path, file_type)

        if self._docling is None:
            raise RuntimeError(
                "Docling غير متاح. ثبّت الحزمة: pip install 'docling[PDFS]' "
                "أو استخدم ملف نصي بسيط (.md/.txt)."
            )
        result = self._docling.convert(str(file_path))
        dl_doc = result.document

        # بعض إصدارات Docling تعيد عناصر iterate_items ككائنات PictureItem
        # دون نص قابل للقراءة. تصدير Markdown هو المسار الرسمي الأكثر ثباتاً
        # للنص والجداول، ويمنع فهرسة تمثيل Python الداخلي للكائنات.
        if hasattr(dl_doc, "export_to_markdown"):
            try:
                markdown = (dl_doc.export_to_markdown() or "").strip()
                if len(markdown) >= 80:
                    heading_blocks = []
                    for line in markdown.splitlines():
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            level = len(stripped) - len(stripped.lstrip("#"))
                            heading_blocks.append(
                                HeadingBlock(level=max(0, min(level - 1, 6)), text=stripped.lstrip("# "), page=1)
                            )
                    return ParsedDocument(
                        title=file_path.stem,
                        file_path=str(file_path),
                        file_type=file_type,
                        pages=[PageBlock(page_number=1, text=markdown)],
                        headings=heading_blocks,
                        word_count=len(markdown.split()),
                        metadata={"parser": "docling_markdown"},
                    )
            except Exception:
                logger.exception("فشل تصدير Markdown من Docling؛ استخدام مسار العناصر البديل")

        pages: List[PageBlock] = []
        headings: List[HeadingBlock] = []
        word_count = 0

        # تجميع النص حسب الصفحات
        page_texts: Dict[int, List[str]] = {}
        page_tables: Dict[int, List[TableBlock]] = {}
        page_images: Dict[int, int] = {}

        try:
            # Docling يعرض pages عبر document.pages إن وُجدت
            from docling.document_converter import DocumentConverter  # noqa
            for page in dl_doc.pages:
                page_texts.setdefault(page.page_no, []).append("")
        except Exception:
            pass

        # المسار الأضمن: traversing blocks
        # لا نعتمد على ItemRef لأن هذا الرمز تغيّر بين إصدارات Docling.
        current_page = 1
        for block in dl_doc.iterate_items():
            block_type = getattr(block, "label", None) or type(block).__name__
            page_no = getattr(block, "page_no", current_page) or current_page

            if block_type in ("Title", "SectionHeader", "SectionHeader1",
                              "SectionHeader2", "SectionHeader3", "SectionHeader4"):
                level = max(0, int(str(block_type)[-1]) - 1) if block_type.startswith("SectionHeader") and block_type[-1].isdigit() else (0 if block_type == "Title" else 1)
                try:
                    txt = block.text if hasattr(block, "text") else str(block)
                except Exception:
                    txt = str(block)
                headings.append(HeadingBlock(level=level, text=txt, page=page_no))
            elif block_type == "Table":
                rows: List[List[str]] = []
                try:
                    for row in block.data.table_cells if hasattr(block, "data") else []:
                        pass
                    grid = block.export_to_dataframe() if hasattr(block, "export_to_dataframe") else None
                    if grid is not None:
                        rows = [[str(c) for c in r] for r in grid.values.tolist()]
                except Exception:
                    pass
                if rows:
                    page_tables.setdefault(page_no, []).append(
                        TableBlock(caption="", rows=rows)
                    )
            elif block_type == "Picture":
                page_images[page_no] = page_images.get(page_no, 0) + 1
            else:
                try:
                    txt = block.text if hasattr(block, "text") else str(block)
                except Exception:
                    txt = str(block)
                if txt and txt.strip():
                    page_texts.setdefault(page_no, []).append(txt)

        # بناء الصفحات بترتيب أرقامها
        all_page_nos = sorted(
            set(page_texts) | set(page_tables) | set(page_images) | {1}
        )
        for pno in all_page_nos:
            lines = page_texts.get(pno, [])
            text = "\n".join(lines)
            tables = page_tables.get(pno, [])
            for t in tables:
                text += "\n\n[TABLE]\n" + t.to_text() + "\n[/TABLE]"
            word_count += len(text.split())
            pages.append(
                PageBlock(
                    page_number=pno,
                    text=text,
                    tables=tables,
                    images=page_images.get(pno, 0),
                )
            )

        title = Path(file_path).stem
        metadata = {
            "file_type": file_type,
            "page_count": len(pages),
            "heading_count": len(headings),
            "table_count": sum(len(t) for t in page_tables.values()),
            "image_count": sum(page_images.values()),
        }

        return ParsedDocument(
            title=title,
            file_path=str(file_path),
            file_type=file_type,
            pages=pages,
            headings=headings,
            word_count=word_count,
            metadata=metadata,
        )

    # ── وضع تجريبي: تخليص النصوص البسيطة دون Docling ────────
    def _parse_plain_text(self, file_path: Path, file_type: str) -> ParsedDocument:
        """تخليص .md/.txt بعناوينها (يحدد العناوين بـ# والخطوط الفاصلة).

        Plain-text fallback when Docling is unavailable.
        """
        import re

        raw = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        text_lines: List[str] = []
        headings: List[HeadingBlock] = []
        title = Path(file_path).stem
        first_heading = True

        for raw_line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)$", raw_line.strip())
            if m:
                level = len(m.group(1)) - 1
                text = m.group(2).strip()
                headings.append(HeadingBlock(level=level, text=text, page=1))
                if first_heading:
                    title = text
                    first_heading = False
                text_lines.append("")
            elif raw_line.strip() == "---":
                text_lines.append("")
            else:
                text_lines.append(raw_line)

        text = "\n".join(l.rstrip() for l in text_lines)
        word_count = len(text.split())
        return ParsedDocument(
            title=title,
            file_path=str(file_path),
            file_type=file_type,
            pages=[PageBlock(page_number=1, text=text)],
            headings=headings,
            word_count=word_count,
            metadata={
                "file_type": file_type,
                "page_count": 1,
                "heading_count": len(headings),
                "plain_text_fallback": True,
            },
        )
