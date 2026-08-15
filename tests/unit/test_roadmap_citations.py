import pytest

from app.knowledge.validator import CitationValidator


def valid_path():
    return {
        "source_id": "src-1",
        "modules": [
            {
                "module_id": "module-1",
                "source_citations": [
                    {
                        "source_id": "src-1",
                        "chunk_id": "chunk-1",
                        "quote": "Python لغة برمجة عالية المستوى.",
                    }
                ],
            }
        ],
    }


def test_roadmap_citations_are_valid():
    chunks = [{"chunk_id": "chunk-1", "text": "Python لغة برمجة عالية المستوى."}]
    assert CitationValidator(chunks, "src-1").validate(valid_path()) == []


def test_validator_rejects_unknown_chunk_and_source():
    path = valid_path()
    path["modules"][0]["source_citations"][0].update(
        {"source_id": "src-other", "chunk_id": "missing", "quote": "غير موجود"}
    )
    issues = CitationValidator(
        [{"chunk_id": "chunk-1", "text": "نص مختلف"}], "src-1"
    ).validate(path)
    assert any("مصدر غير صحيح" in issue for issue in issues)
    assert any("مقطع غير موجود" in issue for issue in issues)


def test_validator_rejects_quote_not_in_chunk():
    path = valid_path()
    path["modules"][0]["source_citations"][0]["quote"] = "اقتباس مختلق"
    issues = CitationValidator(
        [{"chunk_id": "chunk-1", "text": "النص الأصلي"}], "src-1"
    ).validate(path)
    assert any("اقتباس غير مطابق" in issue for issue in issues)


def test_validator_requires_citation_per_module():
    path = {"source_id": "src-1", "modules": [{"module_id": "module-1"}]}
    issues = CitationValidator(
        [{"chunk_id": "chunk-1", "text": "نص"}], "src-1"
    ).validate(path)
    assert any("بلا استشهاد" in issue for issue in issues)
