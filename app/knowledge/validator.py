"""
Validation Layer — أدوات التحقق الحتمية على مخرجات LLM.

المبدأ (من وثيقة المشروع):
- التحقق من الـJSON يتم عبر Pydantic/JSON Schema تلقائياً.
- التحقق من المراجع (Citation Accuracy) حتمي:
  كل citation يجب أن يشير إلى chunk_id صالح موجود في المدخلات.
- verify_source: يتحقق أن المعلومة موجودة فعلاً في المقطع المسند
  (مطابقة كلمات أساسية — approximation حتمية دون LLM إضافي).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Dict, List

from app.rag.hybrid_search import _tokenize

logger = logging.getLogger(__name__)


def validate_citations_exist(
    item: Dict[str, Any], valid_chunk_ids: set
) -> List[str]:
    """تأكد أن كل chunk_ids في العنصر تشير إلى مقاطع موجودة."""
    issues: List[str] = []
    for field in ("source_chunk_ids", "evidence_chunk_ids"):
        refs = item.get(field) or []
        missing = [c for c in refs if c not in valid_chunk_ids]
        if missing:
            issues.append(f"reference {field} يشير لمقاطع غير موجودة: {missing[:5]}")
    return issues


def verify_source_claim(claim_text: str, chunk_text: str, threshold: float = 0.6) -> bool:
    """
    تحقق تقريبي حتمي: هل كلمات claim الأساسية موجودة في chunk؟
    (بدون LLM إضافي — تقريب lexically مع معالجة العربية)
    """
    claim_tokens = set(_tokenize(claim_text))
    chunk_tokens = set(_tokenize(chunk_text))
    if not claim_tokens:
        return False
    overlap = len(claim_tokens & chunk_tokens) / len(claim_tokens)
    return overlap >= threshold


def calculate_composite_confidence(
    model_confidence: float,
    evidence_count: int = 0,
    citations_valid: bool = True,
    schema_valid: bool = True,
) -> float:
    """
    درجة ثقة مركبة من عدة إشارات:
    - ثقة النموذج (من extraction)
    - قوة الأدلة (عدد المقاطع المساندة)
    - صحة الاقتباسات
    - صحة schema
    """
    if not schema_valid:
        return 0.0
    evidence_bonus = min(0.15, evidence_count * 0.05)
    citation_factor = 1.0 if citations_valid else 0.7
    score = (model_confidence + evidence_bonus) * citation_factor
    return round(min(1.0, max(0.0, score)), 4)


def validate_json_schema(payload: Any, schema: Dict[str, Any]) -> List[str]:
    """إرجاع قائمة الأخطاء (فارغة = صالح) دون رفع استثناء."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    return [str(e.message) for e in sorted(validator.iter_errors(payload), key=lambda e: list(e.path))]


def check_duplicate_concepts(concepts: List[Dict[str, Any]]) -> List[str]:
    """كشف تكرار الأسماء (case-insensitive + تطبيع)."""
    issues: List[str] = []
    seen: Dict[str, int] = {}
    for c in concepts:
        norm = re.sub(r"[^\w\u0600-\u06FF]+", "", (c.get("name") or "").strip().lower())
        if not norm:
            continue
        seen[norm] = seen.get(norm, 0) + 1
        if seen[norm] > 1:
            issues.append(f"مفهوم مكرر (بعد التطبيع): {c.get('name')}")
    return issues


def _normalize_citation_text(value: str) -> str:
    """Normalize PDF/Unicode artifacts before deterministic citation matching."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) not in {"Cf", "Cc"} or ch in {"\n", "\t"})
    return re.sub(r"\s+", " ", value).strip()


class CitationValidator:
    """تحقق حتمي من استشهادات الوحدات التعليمية."""

    def __init__(self, chunks: List[Dict[str, Any]], source_id: str):
        self.source_id = source_id
        self.chunks = {str(c.get("chunk_id")): c for c in chunks if c.get("chunk_id")}

    def validate(self, learning_path: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        for module in learning_path.get("modules", []):
            citations = module.get("source_citations") or []
            if not citations:
                issues.append(f"module {module.get('module_id', module.get('order'))} بلا استشهاد")
                continue
            for citation in citations:
                if citation.get("source_id") != self.source_id:
                    issues.append(f"مصدر غير صحيح في module {module.get('module_id')}")
                chunk_id = str(citation.get("chunk_id", ""))
                chunk = self.chunks.get(chunk_id)
                if chunk is None:
                    issues.append(f"مقطع غير موجود: {chunk_id}")
                    continue
                quote = (citation.get("quote") or "").strip()
                text = str(chunk.get("text") or chunk.get("content") or "")
                # PDF extraction may add bidi marks, compatibility forms,
                # or line-break whitespace. Compare normalized text while
                # preserving the requirement that the quote exists verbatim
                # in the source content after extraction normalization.
                normalized_quote = _normalize_citation_text(quote)
                normalized_text = _normalize_citation_text(text)
                if not normalized_quote or normalized_quote not in normalized_text:
                    issues.append(f"اقتباس غير مطابق للمقطع: {chunk_id}")
        return issues

    def assert_valid(self, learning_path: Dict[str, Any]) -> None:
        issues = self.validate(learning_path)
        if issues:
            raise ValueError("Citation validation failed: " + "; ".join(issues))
