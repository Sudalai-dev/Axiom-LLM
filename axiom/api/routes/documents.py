"""
On-demand document/export routes.

Documents and export formats are NOT eagerly rendered into every solution
response (that would defeat the "reduce text output" goal) — the response
carries only lightweight catalogs (`documents_catalog`, `export_manifest`).
These routes render one document or export format at a time, looked up by
`solution_id` against the ephemeral solution cache populated by
PresentationRenderer on every `/solution` or `/chat/messages` call.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from ocif.domains import OctagonalModel
from ocif.renderers import document_types
from ocif.renderers import export as export_renderer
from ocif.renderers import solution_cache
from ocif.solution_mapping import SolutionMappingEngine
from ocif.visualization import OctagonalVisualizationEngine

router = APIRouter(prefix="/api/v1/solutions", tags=["Documents"])

_mapping_engine = SolutionMappingEngine()
_visualization_engine = OctagonalVisualizationEngine()


def _load_solution(solution_id: str):
    entry = solution_cache.get(solution_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached solution for '{solution_id}' — it may have expired; re-issue the original request.",
        )
    return entry


@router.get("/{solution_id}/documents")
async def list_documents(
    solution_id: str,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """Lists every document type available for this solution (metadata only)."""
    _load_solution(solution_id)
    return {"solution_id": solution_id, "documents": document_types.catalog()}


@router.get("/{solution_id}/documents/{document_type}")
async def render_document(
    solution_id: str,
    document_type: str,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """Renders one document type (e.g. hld, brd, openapi) from the cached blueprint."""
    doc, _markdown = _load_solution(solution_id)
    try:
        rendered = document_types.render(doc, document_type)
    except KeyError:
        available = ", ".join(d["type"] for d in document_types.catalog())
        raise HTTPException(status_code=404, detail=f"Unknown document type '{document_type}'. Available: {available}")
    return rendered.model_dump()


@router.get("/{solution_id}/export/{fmt}")
async def export_solution(
    solution_id: str,
    fmt: str,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """Exports the solution in one of the manifest's formats."""
    doc, markdown = _load_solution(solution_id)
    manifest = {m["format"]: m for m in export_renderer.export_manifest()}
    entry = manifest.get(fmt)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown export format '{fmt}'.")
    if not entry["available"]:
        raise HTTPException(status_code=501, detail=entry["reason"])

    model = _mapping_engine.map(doc)
    filename = export_renderer.export_filename(doc, fmt)

    if fmt == "markdown":
        content: Any = markdown
    elif fmt == "json":
        content = export_renderer.to_json(doc)
    elif fmt == "html":
        content = export_renderer.to_html(doc, markdown, _visualization_engine.build_svg(model))
    elif fmt == "svg":
        content = _visualization_engine.build_svg(model)
    elif fmt == "mermaid":
        content = _visualization_engine.build_mermaid(model)
    elif fmt == "plantuml":
        content = _visualization_engine.build_plantuml(model)
    elif fmt == "json_graph":
        content = _visualization_engine.build_json_graph(model)
    elif fmt == "reactflow":
        content = _visualization_engine.build_reactflow(model)
    else:
        raise HTTPException(status_code=501, detail=f"Export format '{fmt}' is declared but not wired yet.")

    return {"solution_id": solution_id, "format": fmt, "filename": filename, "content": content}
