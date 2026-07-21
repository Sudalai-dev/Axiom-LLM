"""
Project Intelligence upload route — Phase 6 (Multimodal Project Understanding).

New, additive endpoint: accepts arbitrary uploaded project files (PDF, DOCX,
PPTX, images, ZIP, source code, Markdown, CSV, JSON) alongside an optional
free-text message, extracts their content (multimodal/extractor.py), and
feeds the combined text through the exact same OCIF kernel + presentation
pipeline `/api/v1/solution` uses — so an uploaded project produces the same
Project Intelligence Model, documents, and diagrams a text request would,
regardless of input modality. Does not modify `/api/v1/solution` or
`/api/v1/chat/messages` — this is a new route, not a change to either.

Uploads are never persisted: extraction happens in-memory/temp-file per
request, matching the platform's existing "solutions are ephemeral, derived
on demand" invariant (ocif/renderers/solution_cache.py) — no new database
table is introduced.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.middleware.auth import resolve_security_context
from api.routes.deps import is_developer, kernel
from core.models.base import RequestContext, new_uuid
from multimodal.extractor import MAX_FILES_PER_UPLOAD, build_project_text
from ocif.frames import SolutionDocument
from ocif.renderers import PresentationRenderer

router = APIRouter(prefix="/api/v1/projects", tags=["Project Intelligence"])


@router.post("/analyze")
async def analyze_project(
    message: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    developer_mode: bool = Form(False),
    files: List[UploadFile] = File(default_factory=list),
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """
    Builds one unified Project Intelligence Model from uploaded project
    files (any mix of PDF/DOCX/PPTX/images/ZIP/source code/Markdown/CSV/
    JSON) plus an optional free-text message, then runs the same solution
    pipeline `/api/v1/solution` uses. Returns the identical response shape
    (dashboard-first, with `solution_blueprint`/`octagonal_model`/
    `visualizations`/`generated_documents`/`project_diagrams`), plus an
    additive `ingested_files` summary of what was extracted from each
    uploaded file.
    """
    if not files and not (message and message.strip()):
        raise HTTPException(status_code=400, detail="Provide at least one file or a message.")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=400, detail=f"Too many files (max {MAX_FILES_PER_UPLOAD}).")

    file_payload = [(f.filename or "unnamed", await f.read()) for f in files]
    extracted_text, extraction_results = build_project_text(file_payload)

    combined_parts = [p for p in (message or "", extracted_text) if p and p.strip()]
    combined_message = "\n\n".join(combined_parts)
    if not combined_message.strip():
        raise HTTPException(
            status_code=400,
            detail="No usable text could be extracted from the uploaded file(s) and no message was provided.",
        )

    session_id = session_id or new_uuid()
    output = await kernel.process(
        message=combined_message,
        user_id=req_ctx.user.user_id,
        project="default",
        conversation_id=session_id,
    )

    result: Dict[str, Any] = {
        "solution_id": output.solution_id,
        "session_id": session_id,
        "is_conversational": output.is_conversational,
        "markdown": output.solution_markdown or output.conversational_reply,
        "citations": output.citations,
        "ingested_files": [
            {
                "filename": r.filename,
                "format_category": r.format_category,
                "characters_extracted": len(r.text),
                "note": r.note,
            }
            for r in extraction_results
        ],
    }

    if output.is_conversational:
        result["solution_blueprint"] = None
        result["octagonal_model"] = None
        result["visualizations"] = None
        result["implementation_roadmap"] = None
        result["generated_documents"] = []
        result["dashboard"] = None
        result["documents_catalog"] = []
        result["export_manifest"] = []
        result["project_diagrams"] = []
    else:
        doc = SolutionDocument(**output.solution_json)
        result.update(PresentationRenderer.render(doc, output.solution_markdown))

    if developer_mode and is_developer(req_ctx) and output.trace:
        result["developer"] = {
            "correlation_id": output.correlation_id,
            "confidence": output.confidence,
            "trace": output.trace.model_dump(),
        }

    return result
