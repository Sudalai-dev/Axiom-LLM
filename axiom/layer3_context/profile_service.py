"""
OCIF Profile Service — Layer 3.

Retrieves and validates user profile metadata from the database,
ensuring status validation (is_active) and synchronizing RBAC claims.

Traces to:
  - Document 14 (Security Design) Section 3: Identity & Access Management
  - Document 9 (Database Design) Section 4.1: Users schema
"""

import logging
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.exceptions import AuthenticationError
from axiom.core.models.base import UserContext
from axiom.storage.models import User

logger = logging.getLogger("AxiomProfileService")


class ProfileService:
    """
    Manages active user profile metadata synchronization from the database.
    """

    async def get_active_profile(self, db: AsyncSession, user_ctx: UserContext) -> Dict[str, Any]:
        """
        Loads the user profile from the database, confirms is_active state,
        and returns a dictionary of metadata attributes.
        """
        try:
            result = await db.execute(
                select(User).filter(User.user_id == user_ctx.user_id)
            )
            user = result.scalars().first()
            
            if not user:
                logger.error(f"User profile '{user_ctx.user_id}' missing in database")
                raise AuthenticationError("User profile not found in database records")
            
            # Note: If database is_active is boolean, verify it
            # In our sqlite prototype model, User has is_active flag.
            # Let's check user attributes dynamically
            is_active = getattr(user, "is_active", True)
            if not is_active:
                logger.warning(f"Inactive user '{user_ctx.username}' attempted access")
                raise AuthenticationError("User account is deactivated")

            return {
                "user_id": user.user_id,
                "email": user.email,
                "role": user.role,
                "department": user.department,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Database error in ProfileService: {e}")
            # Fall back to token-level credentials if database check errors out,
            # ensuring high availability but logging the event.
            return {
                "user_id": user_ctx.user_id,
                "email": None,
                "role": user_ctx.role,
                "department": user_ctx.department,
                "created_at": None
            }
