"""
Ufuq AI Engine — نقطة الدخول الرئيسية (FastAPI).
Main entry point for the Ufuq AI Engine (FastAPI).

```text
                 Ufuq AI Engine
 ┌───────────────────────────────────────────────────┐
 │  POST /sources/upload       →  رفع مستند           │
 │  POST /sources/url          →  رابط/URL            │
 │  POST /jobs                 →  مهمة Agent          │
 │  GET  /jobs/{id}            →  حالة المهمة         │
 │  POST /jobs/{id}/review     →  مراجعة بشرية        │
 │  POST /rag/search           →  بحث RAG هجين        │
 │  GET  /knowledge/{id}       →  Knowledge Graph     │
 │  GET  /learning/{id}/path   →  مسار التعلم         │
 │  GET  /health               →  فحص الصحة           │
 │  GET  /mcp/tools            →  أدوات MCP           │
 └───────────────────────────────────────────────────┘
```
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

logger = logging.getLogger(__name__)

# تفعيل وضع CI من متغير البيئة مباشرة (للتطوير والاختبار)
import os as _os

if _os.getenv("CI_MODE", "").lower() in ("1", "true", "yes"):
    _os.environ.setdefault("CI_MODE", "true")

app = FastAPI(
    title="Ufuq AI Engine",
    description=(
        "محرك الذكاء الاصطناعي لمنصة أُفق التعليمية — "
        "تحويل المستندات إلى خرائط معرفية ومسارات تعلم."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تسجيل كل الـroutes
from app.api.routes_jobs import router as jobs_router
from app.api.routes_knowledge import router as knowledge_router
from app.api.routes_rag import router as rag_router
from app.api.routes_sources import router as sources_router

app.include_router(jobs_router)
app.include_router(sources_router)
app.include_router(rag_router)
app.include_router(knowledge_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Processing-Time"] = f"{time.time() - start:.3f}s"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("خطأ غير متوقع: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


@app.get("/health")
async def health() -> dict:
    """فحص الصحة — يعتمد على إعدادات LLM والنماذج المتاحة."""
    from app.config import get_settings

    settings = get_settings()
    status = {
        "status": "ok",
        "provider": settings.llm_provider,
        "embedding_model": settings.embedding_model,
        "local_mode": settings.is_local_mode(),
        "ci_mode": settings.ci_mode,
    }
    if settings.is_local_mode():
        # تحقق اختياري من أن Ollama يعمل
        try:
            import urllib.request

            with urllib.request.urlopen(
                f"{settings.ollama_base_url}/api/tags", timeout=3
            ) as resp:
                status["ollama"] = "available"
        except Exception:
            status["ollama"] = "unavailable"
    return status


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("app/static/index.html")
