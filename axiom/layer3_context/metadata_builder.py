"""
OCIF Metadata Builder — Layer 3.

Consolidates intent parameters, named entities, conversation memory, profile traits,
and injected heuristics into the canonical ContextFrame DTO (per Doc 7 Section 4).

Traces to:
  - Document 7 (LLD) Section 4: Context Layer contract
  - Document 12 (Prompt Engineering Guide) Section 3: Standard prompt context
"""

import logging
from typing import List, Dict, Any

from axiom.core.models.base import RequestContext
from axiom.core.models.context import (
    ContextFrame, EntityInfo, ConversationMemory,
)

logger = logging.getLogger("AxiomMetadataBuilder")


class MetadataBuilder:
    """
    Assembles the multi-dimensional ContextFrame payload.
    """

    HEURISTICS_BY_INTENT = {
        "CodeGen": [
            "Write clear, type-annotated, PEP-8 compliant Python code.",
            "Always include robust try-except error handling and use structured logging.",
            "Write units tests for any helper function or logic defined.",
            "Never generate placeholders, TODOs, or mock implementation blocks."
        ],
        "ArchitectureReview": [
            "Ensure designs strictly align with the OCIF 8-Layer architecture model.",
            "Identify boundaries, event DTO contracts, and transactional isolation zones.",
            "Map dependencies sequentially: Layer 7 Decision must gate all state mutations."
        ],
        "SystemAdmin": [
            "Verify caller roles against the standard identity governance RBAC matrix.",
            "Set explicit risk scores and require hitl approvals for financial or irreversible changes.",
            "Confirm that audit log writes succeed before running system changes."
        ],
        "GeneralQ&A": [
            "Answer questions using only the provided knowledge context.",
            "Express confidence limits clearly and flag uncertainty when data is missing.",
            "Cite sources directly using chunk UUID reference labels."
        ]
    }

    def build_frame(
        self,
        request_context: RequestContext,
        intent: str,
        intent_confidence: float,
        requires_clarification: bool,
        entities: List[EntityInfo],
        memory: ConversationMemory,
        profile_data: Dict[str, Any]
    ) -> ContextFrame:
        """
        Synthesizes individual components into a complete ContextFrame object.
        """
        # Determine heuristics based on resolved intent
        injected_heuristics = self.HEURISTICS_BY_INTENT.get(intent, self.HEURISTICS_BY_INTENT["GeneralQ&A"])

        # Define default system constraints per Doc 7 Section 4
        system_constraints = [
            "Enforce tenant data isolation boundaries on all database/vector operations.",
            "Execute Python code only inside the redirected stdout sandbox execution engine.",
            "Fail-closed: any ambiguous policy rule logic must terminate in blocked outcomes."
        ]

        # Construct ContextFrame
        frame = ContextFrame(
            intent=intent,
            intent_confidence=intent_confidence,
            requires_clarification=requires_clarification,
            entities=entities,
            memory=memory,
            system_constraints=system_constraints,
            injected_heuristics=injected_heuristics,
            request_context=request_context
        )

        logger.debug(f"Successfully assembled ContextFrame '{frame.frame_id}' for query intent '{intent}'")
        return frame
