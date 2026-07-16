"""Chat routes — conversational entrypoint into the OCIF kernel.

Engineering requests no longer return plain text alone: the response also
carries the Octagonal Engineering Visualization of the solution (the same
structured payload `/solution` returns), so the primary chat surface shows
how the solution is organized, not just a markdown blob. Trivial
clarifications still get a plain conversational reply with no blueprint."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.middleware.auth import resolve_security_context
from api.routes.deps import (
    DEFAULT_PROJECT, gate_agent_request, is_developer, kernel, record_agent_usage,
)
from core.models.base import RequestContext, new_uuid
from ocif.frames import SolutionDocument
from ocif.renderers import PresentationRenderer

router = APIRouter(prefix="/api/v1", tags=["Chat"])


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    solution_id: Optional[str] = None
    response: str
    citations: List[Dict[str, str]] = Field(default_factory=list)
    confidence: Optional[float] = None
    is_conversational: bool = True
    octagonal_model: Optional[Dict[str, Any]] = None
    visualizations: Optional[Dict[str, Any]] = None
    implementation_roadmap: Optional[Dict[str, Any]] = None
    generated_documents: List[Dict[str, Any]] = Field(default_factory=list)
    # Dashboard-first payload (2026-07 addition) — a client should prefer this
    # over `response`/`markdown` for the primary view; the full report stays
    # available above and via `documents_catalog` for anything that wants it.
    dashboard: Optional[Dict[str, Any]] = None
    documents_catalog: List[Dict[str, Any]] = Field(default_factory=list)
    export_manifest: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/chat/messages", response_model=ChatResponse)
async def chat_message(
    req: ChatRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> ChatResponse:
    """
    Processes a chat message through the OCIF kernel. Engineering requests
    get a complete Solution Blueprint + Octagonal Visualization; trivial
    clarifications get a plain conversational reply. Internal confidence is
    only surfaced to platform admins.
    """
    session_id = req.session_id or new_uuid()

    # Freemium gate: blocks (402) when a free user is out of daily quota and
    # returns which provider to serve this request with (OpenCode for free).
    provider_override = await gate_agent_request(req_ctx)

    output = await kernel.process(
        message=req.message,
        user_id=req_ctx.user.user_id,
        tenant_id=req_ctx.tenant.tenant_id,
        project=DEFAULT_PROJECT,
        conversation_id=session_id,
        attachments=req.attachments,
        provider_override=provider_override,
    )

    await record_agent_usage(req_ctx, output)

    response = ChatResponse(
        session_id=session_id,
        solution_id=output.solution_id if not output.is_conversational else None,
        response=output.conversational_reply if output.is_conversational else output.solution_markdown,
        citations=output.citations,
        confidence=output.confidence if is_developer(req_ctx) else None,
        is_conversational=output.is_conversational,
    )

    if not output.is_conversational:
        doc = SolutionDocument(**output.solution_json)
        package = PresentationRenderer.render(doc, output.solution_markdown)
        response.octagonal_model = package["octagonal_model"]
        response.visualizations = package["visualizations"]
        response.implementation_roadmap = package["implementation_roadmap"]
        response.generated_documents = package["generated_documents"]
        response.dashboard = package["dashboard"]
        response.documents_catalog = package["documents_catalog"]
        response.export_manifest = package["export_manifest"]

    return response
