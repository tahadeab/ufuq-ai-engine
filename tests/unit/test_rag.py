"""
اختبارات RAG — RRF fusion وkeyword search وtokenize.
"""

import pytest

from app.rag.hybrid_search import (
    keyword_search_local,
    reciprocal_rank_fusion,
)


class TestTokenize:
    def test_english(self):
        from app.rag.hybrid_search import _tokenize

        tokens = _tokenize("Machine Learning is great")
        assert "machine" in tokens
        assert "learning" in tokens

    def test_arabic(self):
        from app.rag.hybrid_search import _tokenize

        tokens = _tokenize("التعلم الآلي مجال مهم")
        assert "التعلم" in tokens
        assert "الآلي" in tokens

    def test_empty(self):
        from app.rag.hybrid_search import _tokenize

        assert _tokenize("") == []

    def test_mixed(self):
        from app.rag.hybrid_search import _tokenize

        tokens = _tokenize("Machine Learning التعلم الآلي")
        assert len(tokens) >= 3


class TestKeywordSearch:
    def setup_method(self):
        self.chunks = [
            {"chunk_id": "c1", "text": "التعلم الآلي فرع من الذكاء الاصطناعي"},
            {"chunk_id": "c2", "text": "الرياض عاصمة المملكة العربية السعودية"},
            {"chunk_id": "c3", "text": "الشبكات العصبية تحاكي الدماغ البشري"},
        ]

    def test_exact_match_ranks_first(self):
        results = keyword_search_local(self.chunks, "التعلم الآلي", top_k=3)
        assert results[0]["chunk_id"] == "c1"

    def test_no_match_empty(self):
        results = keyword_search_local(self.chunks, "كرة القدم")
        assert results == []

    def test_partial_match(self):
        results = keyword_search_local(self.chunks, "الذكاء")
        assert len(results) >= 1


class TestRRF:
    def test_rrf_ranks_top_agreement_first(self):
        """العنصر الأعلى ترتيباً في القائمتين معاً يفوز بـRRF."""
        vector_list = [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
        keyword_list = [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
        fused = reciprocal_rank_fusion(
            ranked_lists=[vector_list, keyword_list],
            k=60,
        )
        # a: 1/61+1/61 أعلى من b: 1/62+1/62
        assert fused[0]["chunk_id"] == "a"

    def test_rrf_preserves_all(self):
        fused = reciprocal_rank_fusion(ranked_lists=[[{"chunk_id": "x"}]])
        assert len(fused) == 1
        assert "hybrid_score" in fused[0]

    def test_rrf_empty_lists(self):
        fused = reciprocal_rank_fusion(ranked_lists=[[], []])
        assert fused == []

    def test_rrf_weights_affect_result(self):
        """وزن أكبر لقائمة يجعل عنصرها المتفوق يفوز."""
        vector_list = [{"chunk_id": "a"}, {"chunk_id": "b"}]
        keyword_list = [{"chunk_id": "b"}, {"chunk_id": "a"}]
        # بدون أوزان: a وb متساويان (1/61+1/62) — a يأتي أولاً لثبات الترتيب
        neutral = reciprocal_rank_fusion(ranked_lists=[vector_list, keyword_list])
        assert neutral[0]["chunk_id"] == "a"
        # مع وزن أكبر للـkeyword (10x): b يفوز
        weighted = reciprocal_rank_fusion(
            ranked_lists=[vector_list, keyword_list],
            weights=[1.0, 10.0],
        )
        assert weighted[0]["chunk_id"] == "b"
