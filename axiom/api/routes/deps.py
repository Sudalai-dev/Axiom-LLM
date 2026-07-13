"""
Shared route dependencies — singleton services and developer-mode gating.

Every route module imports from here instead of constructing its own kernel
or knowledge service, so the platform has exactly one OctagonalKernel and one
KnowledgeService instance per process.
"""

from core.engine_registry import build_octagonal_kernel
from core.models.base import RequestContext, UserRole
from ecosystem import KnowledgePlatform
from knowledge.service import KnowledgeService
from memory.learning_store import LearningStore

# Singleton services (constructed once at import-time)
knowledge_service = KnowledgeService()

# Durable "learned from past conversations" store — shared by the kernel's
# Memory Engine (recall + persist) and the feedback route (explicit ratings).
learning_store = LearningStore()

# The Engineering Knowledge Platform — AXIOM's durable, graph-ready source of
# engineering intelligence. Seeded once (idempotent) from the in-code knowledge
# so the Engineering Intelligence Engine reads it instead of hardcoded dicts.
knowledge_platform = KnowledgePlatform()
knowledge_platform.seed()

# The OCIF Kernel is stateless per-request but keeps in-process + persistent
# learning memory across requests, so a single shared instance is required.
kernel = build_octagonal_kernel(
    knowledge_service=knowledge_service,
    learning_store=learning_store,
    knowledge_platform=knowledge_platform,
)

# Local-dev single-tenant seed identifiers (see routes/seed.py)
SEED_TENANT_ID = "00000000-0000-0000-0000-000000000001"
SEED_USER_ID = "00000000-0000-0000-0000-000000000002"
SEED_USERNAME = "admin"


def is_developer(req_ctx: RequestContext) -> bool:
    """Developer/Admin mode gate: only platform admins may see internals."""
    role = req_ctx.user.role
    role_value = role.value if hasattr(role, "value") else role
    return role_value == UserRole.PLATFORM_ADMIN.value
