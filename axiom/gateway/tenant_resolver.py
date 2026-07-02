"""
OCIF Tenant Resolver — Layer 2.

Manages database session RLS boundary settings (app.current_tenant)
and validates multi-tenant data access security (per Doc 9 Section 3).

Traces to:
  - Document 9 (Database Design) Section 3: Multi-Tenancy Model
  - Document 14 (Security Design) Section 4: Tenant Data Isolation
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.exceptions import TenantIsolationError

logger = logging.getLogger("AxiomTenantResolver")


async def bind_tenant_to_database_session(db: AsyncSession, tenant_id: str) -> None:
    """
    Sets the database session context variable 'app.current_tenant' to enforce
    Row-Level Security (RLS) policies inside PostgreSQL transactions.
    
    Per Document 9 Section 3:
    "tenant_id = current_setting('app.current_tenant')::uuid"
    
    If running local-first on SQLite, logs isolation and skips pg session variables.
    """
    bind = db.bind
    dialect_name = bind.dialect.name if bind else "unknown"

    if dialect_name == "postgresql":
        try:
            # Set the parameter using SET LOCAL so it is scoped to the current transaction only
            await db.execute(
                text("SET LOCAL app.current_tenant = :tenant_id"),
                {"tenant_id": tenant_id}
            )
            logger.debug(f"Bound database RLS session context variable app.current_tenant = {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to set postgres RLS session variable app.current_tenant: {e}")
            raise TenantIsolationError("Failed to establish tenant security context in database transaction")
    else:
        # SQLite or other local fallback development engines
        logger.debug(f"SQLite dialect detected. Manual query filtering is enforced since RLS is unavailable for tenant {tenant_id}")


def verify_tenant_isolation(context_tenant_id: str, record_tenant_id: str) -> None:
    """
    Cross-checks tenant ownership boundaries at the application service level.
    Raises TenantIsolationError if tenant context mismatch is detected.
    """
    if context_tenant_id != record_tenant_id:
        logger.critical(
            f"Tenant Isolation Violation: Active context tenant {context_tenant_id} attempted "
            f"to read/write data belonging to tenant {record_tenant_id}!"
        )
        raise TenantIsolationError("Access to the requested resource is denied due to tenant boundary constraints")
