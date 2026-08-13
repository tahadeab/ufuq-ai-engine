"""
Routes: Knowledge & Learning & MCP.

GET  /knowledge/{source_id}       → الرسم المعرفي لمصدر
GET  /knowledge/{source_id}/concepts → قائمة المفاهيم
GET  /learning/{source_id}/path   → مسار التعلم
POST /mcp/call                    → استدعاء أداة MCP (للاختبار/الدمج)
GET  /mcp/tools                   → قائمة أدوات MCP
"""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.mcp_server.server import UfuqMCPServer
from app.services.job_store import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge", "learning", "mcp"])


@router.get("/knowledge/{source_id}")
async def get_knowledge_graph(source_id: str) -> Dict:
    """جلب الرسم المعرفي من آخر مهمة ناجحة لهذا المصدر."""
    store = get_job_store()
    for job in store._jobs.values():
        if job.source_id == source_id and job.status == "review_required":
            return job.graph or {}
    raise HTTPException(status_code=404, detail="لا يوجد رسم معرفي لهذا المصدر")


@router.get("/knowledge/{source_id}/concepts")
async def get_concepts(source_id: str) -> Dict:
    store = get_job_store()
    for job in store._jobs.values():
        if job.source_id == source_id and job.status == "review_required":
            return {"concepts": job.concepts or [], "count": len(job.concepts or [])}
    raise HTTPException(status_code=404, detail="لا توجد مفاهيم لهذا المصدر")


@router.get("/learning/{source_id}/path")
async def get_learning_path(source_id: str) -> Dict:
    store = get_job_store()
    for job in store._jobs.values():
        if job.source_id == source_id and job.status == "review_required":
            return job.learning_path or {}
    raise HTTPException(status_code=404, detail="لا يوجد مسار تعلم لهذا المصدر")


@router.get("/learning/{source_id}/lessons")
async def get_lessons(source_id: str) -> Dict:
    store = get_job_store()
    for job in store._jobs.values():
        if job.source_id == source_id and job.status == "review_required":
            return {"lessons": job.lessons or [], "count": len(job.lessons or [])}
    raise HTTPException(status_code=404, detail="لا توجد دروس لهذا المصدر")


# ── MCP ──────────────────────────────────────────────────────
class MCPCallRequest(BaseModel):
    tool: str
    arguments: Dict = {}


class _MCPApiBridge:
    """جسر يبسّط استدعاءات API الداخلي لمخدّم MCP."""

    async def hybrid_search(self, source_id: str, query: str, top_k: int) -> Dict:
        from app.rag.retriever import DocumentRetriever

        retriever = DocumentRetriever()
        results = await retriever.retrieve(query=query, source_id=source_id or "", top_k=top_k)
        return {"results": results, "count": len(results)}

    async def get_learning_path(self, source_id: str) -> Dict:
        store = get_job_store()
        for job in store._jobs.values():
            if job.source_id == source_id:
                return job.learning_path or {}
        return {}

    async def get_concept(self, source_id: str, concept_name: str) -> Dict:
        store = get_job_store()
        for job in store._jobs.values():
            if job.source_id == source_id:
                for c in job.concepts or []:
                    if c.get("name") == concept_name:
                        return {"concept": c}
        return {"error": "concept not found"}

    async def recommend_course(self, source_id: str, concept_name: str, max_recommendations: int) -> Dict:
        store = get_job_store()
        for job in store._jobs.values():
            if job.source_id == source_id:
                related = [
                    {"concept": c.get("name"), "type": c.get("type")}
                    for c in job.concepts or []
                    if c.get("name") != concept_name
                ]
                return {"recommendations": related[:max_recommendations]}
        return {"recommendations": []}


_mcp = UfuqMCPServer(api_client=_MCPApiBridge())


@router.get("/mcp/tools")
async def list_mcp_tools() -> Dict:
    return {"tools": _mcp.tools}


@router.post("/mcp/call")
async def call_mcp_tool(request: MCPCallRequest) -> Dict:
    result = await _mcp.handle_call(request.tool, request.arguments)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
