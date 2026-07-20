"""Solution routes — machine-readable engineering solutions + developer trace."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.middleware.auth import resolve_security_context
from api.routes.deps import (
    DEFAULT_PROJECT, enforce_rate_limit, is_developer, kernel, record_usage,
)
from core.models.base import RequestContext, new_uuid
from ocif.frames import SolutionDocument
from ocif.renderers import PresentationRenderer

router = APIRouter(prefix="/api/v1", tags=["Solution"])


class SolutionRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    developer_mode: bool = Field(
        default=False,
        description="Include the cognitive execution trace + octagon diagram (platform admins only)",
    )


@router.post("/solution")
async def create_solution(
    req: SolutionRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """
    Produces a Solution Dashboard (short executive summary, octagon
    navigation, roadmap overview, document/download catalogs) plus the full
    Solution Blueprint, Octagonal Visualization, and generated documents
    behind it — the primary AXIOM output for every user. The eight
    Octagonal domains describe how the SOLUTION is organized (requirements,
    planning, standards, architecture, rationale, quality, operations),
    never how AXIOM reasoned about it. `dashboard` is the lightweight,
    text-reduced payload a client should render first; `solution_blueprint`/
    `octagonal_model`/`visualizations`/`generated_documents` remain fully
    present for existing consumers and for drill-down into any one domain.

    `developer_mode=true` additionally returns the internal cognitive
    execution trace — platform admins only; the flag is silently ignored
    for any other role, and is entirely separate from the Octagonal
    Visualization above (which every user receives).
    """
    session_id = req.session_id or new_uuid()

    enforce_rate_limit(req_ctx)

    output = await kernel.process(
        message=req.message,
        user_id=req_ctx.user.user_id,
        tenant_id=req_ctx.tenant.tenant_id,
        project=DEFAULT_PROJECT,
        conversation_id=session_id,
        attachments=req.attachments,
    )

    await record_usage(req_ctx, output)

    result: Dict[str, Any] = {
        "solution_id": output.solution_id,
        "session_id": session_id,
        "is_conversational": output.is_conversational,
        "markdown": output.solution_markdown or output.conversational_reply,
        "citations": output.citations,
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
    else:
        doc = SolutionDocument(**output.solution_json)
        result.update(PresentationRenderer.render(doc, output.solution_markdown))
        result["reasoning"] = output.reasoning_thinking or None

    if req.developer_mode and is_developer(req_ctx) and output.trace:
        result["developer"] = {
            "correlation_id": output.correlation_id,
            "confidence": output.confidence,
            "trace": output.trace.model_dump(),
        }

    return result
