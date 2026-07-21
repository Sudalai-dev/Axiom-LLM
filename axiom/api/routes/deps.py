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

# Learning-memory project bucket. The durable learning store is keyed by
# (user_id, project); a single stable bucket per deployment lets the Memory
# Engine recall a user's earlier solutions across conversations. Named here
# (rather than the literal "default" repeated in each route) so the scope is
# defined in one place.
DEFAULT_PROJECT = "default"

# Local-dev seed identifiers (see routes/seed.py)
SEED_USER_ID = "00000000-0000-0000-0000-000000000002"
SEED_USERNAME = "admin"


def is_developer(req_ctx: RequestContext) -> bool:
    """Developer/Admin mode gate: only platform admins may see internals."""
    role = req_ctx.user.role
    role_value = role.value if hasattr(role, "value") else role
    return role_value == UserRole.PLATFORM_ADMIN.value


def enforce_rate_limit(req_ctx: RequestContext) -> None:
    """Per-user token-bucket rate limiting on the expensive agent endpoints.

    Raises RateLimitExceededError (429), mapped by the gateway's RFC 7807
    handler. Not part of "billing/free-limit" — a general abuse guard.
    """
    from api.middleware.rate_limiter import rate_limiter
    rate_limiter.check_rate_limit(req_ctx.user.user_id, "standard")


async def record_usage(req_ctx: RequestContext, output) -> None:
    """Records real usage metrics after a solution (for the dashboard).

    Only non-conversational (real solution) outputs are metered. Best-effort:
    metering must never break the request path.
    """
    if getattr(output, "is_conversational", False):
        return
    try:
        from api.routes.usage import record_solution_usage
        await record_solution_usage(req_ctx, output)
    except Exception:
        pass
