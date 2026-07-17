"""
API route modules — one file per feature area, aggregated into a single
router mounted by axiom.api.gateway.create_gateway_app().
"""

from fastapi import APIRouter

from api.routes import (
    admin, approvals, auth, chat, dashboard, documents, feedback,
    knowledge, knowledge_platform, project_intelligence, solution,
)

router = APIRouter()
for module in (
    auth, chat, solution, feedback, dashboard, documents, approvals, admin,
    knowledge, knowledge_platform, project_intelligence,
):
    router.include_router(module.router)

__all__ = ["router"]
