import pytest

from app.tools import learning_tools


class FakeLLM:
    async def generate_json(self, messages, schema, temperature=0.3):
        return {
            "modules": [
                {
                    "module_id": "module-1",
                    "title": "مقدمة في Python",
                    "description": "أساسيات Python",
                    "learning_objectives": ["شرح الأساسيات"],
                }
            ]
        }


@pytest.mark.asyncio
async def test_generate_path_builds_grounded_roadmap(monkeypatch):
    monkeypatch.setattr(learning_tools, "get_llm", lambda: FakeLLM())
    graph = {
        "ordered": ["c-1"],
        "nodes": [{
            "id": "c-1",
            "name": "Python",
            "source_chunk_ids": ["chunk-1"],
        }],
        "edges": [],
    }
    chunks = [{"chunk_id": "chunk-1", "text": "Python لغة برمجة."}]

    result = await learning_tools.generate_learning_path(
        graph, "src-1", "Python", chunks=chunks
    )
    path = result["learning_path"]
    assert path["modules"]
    assert path["modules"][0]["order"] == 1
    assert path["modules"][0]["source_citations"][0]["chunk_id"] == "chunk-1"
    assert path["modules"][0]["source_citations"][0]["source_id"] == "src-1"


@pytest.mark.asyncio
async def test_generate_path_rejects_empty_graph(monkeypatch):
    monkeypatch.setattr(learning_tools, "get_llm", lambda: FakeLLM())
    with pytest.raises(ValueError, match="KNOWLEDGE_GRAPH_EMPTY"):
        await learning_tools.generate_learning_path(
            {"ordered": [], "nodes": [], "edges": []}, "src-1", chunks=[]
        )
