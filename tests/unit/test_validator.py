"""
اختبارات طبقة التحقق — citations وconfidence وJSON Schema.
"""

import pytest

from app.knowledge.validator import (
    calculate_composite_confidence,
    check_duplicate_concepts,
    validate_citations_exist,
    validate_json_schema,
    verify_source_claim,
)


class TestCitationValidation:
    def test_valid_citations(self):
        issues = validate_citations_exist(
            {"source_chunk_ids": ["c1", "c2"]}, {"c1", "c2", "c3"}
        )
        assert issues == []

    def test_missing_citations(self):
        issues = validate_citations_exist(
            {"source_chunk_ids": ["c1", "c99"]}, {"c1", "c2"}
        )
        assert len(issues) == 1
        assert "c99" in issues[0]


class TestSourceVerification:
    def test_claim_in_chunk(self):
        chunk = "التعلم الآلي فرع من الذكاء الاصطناعي يتعلم الأنماط من البيانات"
        assert verify_source_claim("التعلم الآلي يتعلم من البيانات", chunk)

    def test_claim_not_in_chunk(self):
        chunk = "الطقس غائم اليوم في الرياض"
        assert not verify_source_claim("الذكاء الاصطناعي يتعلم", chunk)

    def test_empty_claim(self):
        assert not verify_source_claim("", "نص عشوائي")


class TestCompositeConfidence:
    def test_base_confidence(self):
        assert calculate_composite_confidence(0.8) == pytest.approx(0.8, abs=0.01)

    def test_schema_invalid_zero(self):
        assert calculate_composite_confidence(0.9, schema_valid=False) == 0.0

    def test_evidence_boost(self):
        high = calculate_composite_confidence(0.8, evidence_count=5)
        low = calculate_composite_confidence(0.8, evidence_count=0)
        assert high > low

    def test_invalid_citations_penalty(self):
        good = calculate_composite_confidence(0.8, citations_valid=True)
        bad = calculate_composite_confidence(0.8, citations_valid=False)
        assert good > bad

    def test_bounds(self):
        assert 0.0 <= calculate_composite_confidence(1.0, evidence_count=100) <= 1.0
        assert calculate_composite_confidence(-1.0) == pytest.approx(0.0, abs=0.01)


class TestDuplicateDetection:
    def test_no_duplicates(self):
        concepts = [{"name": "التعلم الآلي"}, {"name": "الشبكات العصبية"}]
        assert check_duplicate_concepts(concepts) == []

    def test_case_insensitive_duplicate(self):
        concepts = [{"name": "Machine Learning"}, {"name": "machine learning"}]
        assert len(check_duplicate_concepts(concepts)) == 1

    def test_arabic_normalization_duplicate(self):
        concepts = [{"name": "التعلم الآلي"}, {"name": "التعلم-الآلي"}]
        assert len(check_duplicate_concepts(concepts)) == 1


class TestJsonSchemaValidation:
    def test_valid_payload(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        assert validate_json_schema({"name": "اختبار"}, schema) == []

    def test_missing_required(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        errors = validate_json_schema({}, schema)
        assert len(errors) >= 1

    def test_wrong_type(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "additionalProperties": False,
        }
        errors = validate_json_schema({"count": "not_int"}, schema)
        assert len(errors) >= 1
