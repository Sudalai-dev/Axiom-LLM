"""Knowledge routes — direct search over the user's ingested knowledge base.

Reuses the same embed -> vector search path already wired into the OCIF
Knowledge Engine's retriever (see core/engine_registry.py::build_octagonal_kernel)
so a standalone search returns the same real, user-scoped documents that
back a chat response's citations — nothing fabricated for the UI.
"""

from fastapi import APIRouter, Depends, Query

from api.middleware.auth import resolve_security_context
from api.routes.deps import knowledge_service
from core.models.base import RequestContext

router = APIRouter(prefix="/api/v1", tags=["Knowledge"])


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(..., min_length=1, max_length=500),
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Searches the caller's user-scoped knowledge base for the given query."""
    vector = knowledge_service.embedder.embed(q)
    matches = await knowledge_service.vector_retriever.search_vectors(
        query_vector=vector, user_id=req_ctx.user.user_id, limit=10
    )
    results = []
    for match in matches or []:
        payload = match.get("payload", match)
        text = payload.get("text", "") or ""
        results.append({
            "doc_id": payload.get("doc_id", ""),
            "title": payload.get("title") or "Untitled source",
            "excerpt": text[:400],
            "score": match.get("score"),
        })
    return {"query": q, "results": results}
