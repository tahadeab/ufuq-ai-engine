"""Learning path review and export endpoints."""
from __future__ import annotations

import io
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.services.job_store import get_job_store

router = APIRouter(tags=["exports", "review"])


def _latest(source_id: str):
    store = get_job_store()
    jobs = [j for j in store._jobs.values() if j.source_id == source_id and j.learning_path]
    if not jobs:
        raise HTTPException(status_code=404, detail="لا توجد خارطة تعلم لهذا المصدر")
    return sorted(jobs, key=lambda j: j.created_at or "", reverse=True)[0]


@router.get("/learning/{source_id}/versions")
async def list_versions(source_id: str) -> dict:
    store = get_job_store()
    versions = store._history.get(source_id, [])
    if not versions:
        raise HTTPException(status_code=404, detail="لا توجد إصدارات لهذا المصدر")
    return {"source_id": source_id, "versions": [{"version": v["version"], "job_id": v["job_id"], "created_at": v["created_at"], "quality": v["quality"]} for v in versions]}


@router.get("/learning/{source_id}/review")
async def review_path(source_id: str) -> dict:
    job = _latest(source_id)
    path = job.learning_path or {}
    return {"source_id": source_id, "job_id": job.job_id, "version": job.version, "quality": job.quality or path.get("quality", {}), "modules": path.get("modules", [])}


@router.get("/learning/{source_id}/export.json")
async def export_json(source_id: str):
    job = _latest(source_id)
    return job.learning_path or {}


@router.get("/learning/{source_id}/export.md", response_class=PlainTextResponse)
async def export_markdown(source_id: str):
    path = _latest(source_id).learning_path or {}
    lines = [f"# {path.get('title', 'Learning Roadmap')}", "", path.get("description", ""), ""]
    quality = path.get("quality", {})
    if quality:
        lines += ["## Quality", f"- Overall score: {quality.get('overall_score', 0)}", f"- Citation coverage: {quality.get('citation_coverage', 0)}", f"- Unsupported claims: {quality.get('unsupported_claims', 0)}", ""]
    for i, module in enumerate(path.get("modules", []), 1):
        lines += [f"## {i}. {module.get('title', f'Module {i}')}", "", module.get("description", ""), "", "### Learning objectives"]
        for obj in module.get("learning_objectives", []):
            text = obj if isinstance(obj, str) else obj.get("text", "")
            lines.append(f"- {text}")
        lines += ["", "### Evidence"]
        for citation in module.get("source_citations", []):
            lines.append(f"> [{citation.get('chunk_id')}] {citation.get('quote', '')}")
        lines.append("")
    return "\n".join(lines)


@router.get("/learning/{source_id}/export.pdf")
async def export_pdf(source_id: str):
    from fpdf import FPDF
    path = _latest(source_id).learning_path or {}
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.multi_cell(0, 10, str(path.get("title", "Learning Roadmap")).encode("latin-1", "replace").decode("latin-1"))
    pdf.set_font("Arial", size=11)
    for module in path.get("modules", []):
        pdf.ln(4)
        pdf.multi_cell(0, 7, str(module.get("title", "Module")).encode("latin-1", "replace").decode("latin-1"))
        pdf.multi_cell(0, 6, str(module.get("description", "")).encode("latin-1", "replace").decode("latin-1"))
        for citation in module.get("source_citations", []):
            pdf.multi_cell(0, 6, ("[" + str(citation.get("chunk_id")) + "] " + str(citation.get("quote", ""))).encode("latin-1", "replace").decode("latin-1"))
    data = bytes(pdf.output())
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=roadmap-{source_id}.pdf"})
