from app.knowledge.quality import analyze_learning_path_quality


def _path(objective="Python uses indentation"):
    return {"modules": [{"module_id": "module-1", "concepts_covered": ["python"], "learning_objectives": [objective], "source_citations": [{"source_id": "s1", "chunk_id": "c1", "quote": "Python uses indentation to define blocks."}]}]}


def test_quality_accepts_grounded_objective():
    q = analyze_learning_path_quality(_path(), [{"chunk_id": "c1", "text": "Python uses indentation to define blocks."}], {"nodes": [{"id": "python"}], "edges": []}, "s1")
    assert q["citation_coverage"] == 1.0
    assert q["unsupported_claims"] == 0
    assert q["review_required"] is False


def test_quality_flags_unsupported_objective():
    q = analyze_learning_path_quality(_path("Python is faster than every language"), [{"chunk_id": "c1", "text": "Python uses indentation to define blocks."}], {"nodes": [{"id": "python"}], "edges": []}, "s1")
    assert q["unsupported_claims"] == 1
    assert q["review_required"] is True


def test_quality_flags_missing_citation_chunk():
    path = _path()
    path["modules"][0]["source_citations"][0]["chunk_id"] = "missing"
    q = analyze_learning_path_quality(path, [{"chunk_id": "c1", "text": "Python uses indentation to define blocks."}], None, "s1")
    assert q["citation_issues"]
    assert q["review_required"] is True
