"""
End-to-End Test — Ufuq AI Engine

يختبر التدفق الكامل من رفع مستند حتى مسار التعلم،
باستخدام مستند تجريبي حقيقي وكل مسارات الـAPI العامة.
لا يتطلب Ollama ولا نماذج حقيقية (الـAgent يعمل عبر المسار المتاح).

End-to-end flow: upload → job → rag search → knowledge graph → learning path.
"""

import io
import json
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_DOC = """# Machine Learning Basics / مقدمة في التعلم الآلي

## 1. Introduction / المقدمة

Machine learning (ML) is a branch of artificial intelligence focused on building
systems that learn from data. التعلم الآلي هو فرع من الذكاء الاصطناعي يركز على
بناء أنظمة تتعلم من البيانات.

## 2. Supervised Learning / التعلم المُشرف

In supervised learning, the model learns from labeled examples.
في التعلم المُشرف، يتعلم النموذج من أمثلة موسومة (labeled).
Algorithms include linear regression, decision trees, and neural networks.

## 3. Neural Networks / الشبكات العصبية

Neural networks are inspired by the human brain. They consist of layers of
neurons connected by weighted edges. The backpropagation algorithm adjusts
weights based on prediction errors. الشبكات العصبية مستوحاة من الدماغ البشري
وتتكون من طبقات من العصبونات المتصلة بأوزان.

## 4. Evaluation / التقييم

Models are evaluated using metrics like accuracy, precision, recall, and F1.
Cross-validation helps estimate generalization performance.
يتم تقييم النماذج بمقاييس مثل الدقة والاستدعاء وF1.
"""


def check(name, fn):
    try:
        fn()
        print(f"✓ {name}")
        return True
    except AssertionError as exc:
        print(f"✗ {name}: assertion failed — {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"✗ {name}: {type(exc).__name__}: {exc}")
        return False


def t_root():
    r = client.get("/")
    assert r.status_code == 200, r.status_code
    assert r.json()["name"] == "Ufuq AI Engine"


def t_health():
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["provider"] == "ollama"


def t_mcp_tools():
    r = client.get("/mcp/tools")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    expected = {"search_ufuq_knowledge", "get_learning_path", "get_concept",
                "recommend_course"}
    assert expected <= names, f"missing: {expected - names}"


def t_upload():
    """Upload real test document and verify chunking + vector store."""
    global SOURCE_ID
    files = {"file": ("ml_basics.md", io.BytesIO(SAMPLE_DOC.encode("utf-8")), "text/markdown")}
    r = client.post("/sources/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    SOURCE_ID = data["source_id"]
    assert SOURCE_ID.startswith("src-")
    print(f"    source_id = {SOURCE_ID}")

    # verify metadata stored
    r2 = client.get(f"/sources/{SOURCE_ID}")
    assert r2.status_code == 200, r2.text
    meta = r2.json()
    assert meta["source_id"] == SOURCE_ID
    print(f"    metadata: {json.dumps(meta, ensure_ascii=False)[:200]}")


def t_search_rag():
    """Hybrid RAG search on the indexed document."""
    r = client.post("/rag/search", json={
        "query": "What is supervised learning?",
        "source_id": SOURCE_ID,
        "top_k": 3,
    })
    assert r.status_code == 200, r.text
    results = r.json()
    items = results.get("results", results if isinstance(results, list) else [])
    assert len(items) >= 1, f"no results: {results}"
    top = items[0]
    assert "supervised" in top.get("text", "").lower() or \
        top.get("hybrid_score", 0) > 0
    print(f"    top result score={top.get('hybrid_score', top.get('score', '?'))}")


def t_search_arabic():
    """Arabic query support."""
    r = client.post("/rag/search", json={
        "query": "ما هي الشبكات العصبية؟",
        "source_id": SOURCE_ID,
        "top_k": 2,
    })
    assert r.status_code == 200, r.text
    results = r.json()
    items = results.get("results", results if isinstance(results, list) else [])
    assert len(items) >= 1, f"no arabic results: {results}"
    print("    Arabic search OK")


def t_job():
    """Create an Agent job and track its lifecycle."""
    r = client.post("/jobs", json={
        "source_id": SOURCE_ID, "job_type": "process_source",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    job_id = data["job_id"]
    assert job_id.startswith("job-")
    print(f"    job_id = {job_id}, status={data['status']}")

    deadline = time.time() + 30
    last_status = None
    while time.time() < deadline:
        time.sleep(1)
        r2 = client.get(f"/jobs/{job_id}")
        assert r2.status_code == 200, r2.text
        st = r2.json()
        last_status = st.get("status")
        if last_status in ("completed", "failed", "review_required"):
            break
    print(f"    final status: {last_status}")
    assert last_status in ("completed", "review_required"), last_status


def t_knowledge_graph():
    """Retrieve the knowledge graph."""
    r = client.get(f"/knowledge/{SOURCE_ID}")
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"    nodes={data.get('node_count', len(data.get('nodes', [])))}, "
          f"edges={data.get('edge_count', len(data.get('edges', [])))}")


def t_learning_path():
    """Retrieve the generated learning path."""
    r = client.get(f"/learning/{SOURCE_ID}/path")
    assert r.status_code == 200, r.text
    data = r.json()
    modules = data.get("modules", [])
    print(f"    learning path: title={data.get('title', '?')}, "
          f"modules={len(modules)}")


if __name__ == "__main__":
    SOURCE_ID = None
    results = []
    results.append(check("1. Root endpoint", t_root))
    results.append(check("2. Health check", t_health))
    results.append(check("3. MCP tools", t_mcp_tools))
    results.append(check("4. Upload + chunk + store", t_upload))
    results.append(check("5. RAG search (English)", t_search_rag))
    results.append(check("6. RAG search (Arabic)", t_search_arabic))
    results.append(check("7. Agent job lifecycle", t_job))
    results.append(check("8. Knowledge graph", t_knowledge_graph))
    results.append(check("9. Learning path", t_learning_path))

    passed = sum(results)
    print(f"\n{'='*40}\n{passed}/{len(results)} E2E checks passed")
    raise SystemExit(0 if passed == len(results) else 1)
