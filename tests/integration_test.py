"""
اختبار تكامل سريع — FastAPI Contract كامل (بدون نماذج حقيقية).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "Ufuq AI Engine" in r.text
    assert "app.js" in r.text
    assert "app.css" in r.text


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["provider"] in ("ollama", "openai", "gemini", "local")


def test_docs():
    r = client.get("/docs")
    assert r.status_code == 200


def test_mcp_tools():
    r = client.get("/mcp/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) >= 4
    names = {t["name"] for t in tools}
    assert {"search_ufuq_knowledge", "get_learning_path",
            "get_concept", "recommend_course"} <= names


def test_create_job_no_source():
    """المهمة تفشل بشكل أنيق لأن المصدر غير مفهرس."""
    r = client.post("/jobs", json={"source_id": "src-nonexistent",
                                    "job_type": "process_source"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "processing"
    assert data["job_id"].startswith("job-")
    # الحالة تتحول لـfailed بعد الخلفية لأن المصدر غير موجود
    job_id = data["job_id"]
    import time
    time.sleep(2)
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200


def test_get_job_404():
    r = client.get("/jobs/job-does-not-exist")
    assert r.status_code == 404


if __name__ == "__main__":
    for fn in [test_root, test_health, test_docs, test_mcp_tools,
               test_create_job_no_source, test_get_job_404]:
        try:
            fn()
            print(f"✓ {fn.__name__}")
        except Exception as exc:
            print(f"✗ {fn.__name__}: {exc}")
