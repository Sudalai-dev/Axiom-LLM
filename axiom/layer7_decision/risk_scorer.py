"""
OCIF Risk Scorer — Layer 7 (META CORE).

Computes composite action risk ratings based on action payload properties,
tool registry declarations, and actor RBAC roles (per Doc 6 Section 6.3).

Traces to:
  - Document 6 (LLD) Section 6.3: Risk Assessment
  - Document 13 (Agent Design) Section 5: Tool Invocation Protocol
"""

import logging
from typing import Dict, Any

from axiom.core.config import settings
from axiom.core.models.base import UserRole, RiskLevel

logger = logging.getLogger("AxiomRiskScorer")


class RiskScorer:
    """
    Computes composite action risk score vectors.
    """

    ROLE_RISK_WEIGHTS = {
        UserRole.END_USER: 0.60,
        UserRole.PROCESS_OWNER: 0.30,
        UserRole.COMPLIANCE_OFFICER: 0.10,
        UserRole.TENANT_ADMIN: 0.05,
        UserRole.PLATFORM_ADMIN: 0.00
    }

    def calculate_risk(
        self,
        action_type: str,
        payload: Dict[str, Any],
        user_role: UserRole,
        tool_risk_level: str = "low"
    ) -> float:
        """
        Calculates composite risk score (0.0-1.0).
        
        Formula:
        Risk = (Base_Tool_Risk * 0.70) + (User_Role_Risk * 0.30)
        
        Also checks value multipliers (e.g., transaction amounts).
        """
        # Determine Base Tool Risk
        if tool_risk_level == "high":
            base_risk = 0.85
        elif tool_risk_level == "medium":
            base_risk = 0.50
        else:
            base_risk = 0.10

        # Adjust base risk if transaction parameters are present (e.g. monetary limits)
        if "amount" in payload:
            try:
                amount = float(payload["amount"])
                if amount > 1000.0:
                    base_risk = max(base_risk, 0.90)
                elif amount > 500.0:
                    base_risk = max(base_risk, 0.70)
                elif amount > 100.0:
                    base_risk = max(base_risk, 0.40)
            except Exception:
                pass

        # Resolve User Role Risk multiplier
        role_str = user_role.value if hasattr(user_role, "value") else str(user_role)
        role_risk = self.ROLE_RISK_WEIGHTS.get(role_str, self.ROLE_RISK_WEIGHTS.get(user_role, 0.50))

        # Composite score calculation
        composite_risk = (base_risk * 0.70) + (role_risk * 0.30)
        
        # Clip between 0.0 and 1.0
        composite_risk = max(0.0, min(1.0, float(composite_risk)))

        logger.info(
            f"Calculated composite risk score: {composite_risk:.2f} "
            f"(Tool: {tool_risk_level}, User role: {role_str})"
        )
        return composite_risk

