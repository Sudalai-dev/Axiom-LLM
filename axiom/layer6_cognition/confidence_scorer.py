"""
OCIF Confidence Scorer — Layer 6.

Analyzes generated model completions to extract structured confidence variables
and formats the explainability trace logs (per Doc 4 FR-603/FR-604).

Traces to:
  - Document 4 (SRS) FR-603: Confidence scoring
  - Document 4 (SRS) FR-604: Explainability trace
  - Document 12 (Prompt Engineering Guide) Section 7: Anti-patterns (uncertainty flagging)
"""

import logging
import re
from typing import Dict, Any, Tuple


logger = logging.getLogger("AxiomConfidenceScorer")


class ConfidenceScorer:
    """
    Evaluates response tokens and extracts confidence and trace info.
    """

    def calculate_score(self, content: str, provider_score: float) -> Tuple[float, str]:
        """
        Calibrates model self-reported confidence against response properties.
        Scans for semantic markers indicating doubt, hedging, or lack of grounding.
        
        Returns: (calibrated_confidence, reasoning_trace)
        """
        # Default starting point is the provider self-reported score
        score = provider_score

        # List of doubt/uncertainty keywords (hedging markers)
        hedging_patterns = [
            r"\b(unsure|not sure|uncertain|likely|probably|maybe)\b",
            r"\b(do not know|don't know|cannot verify|unable to verify)\b",
            r"\b(might|could be|perhaps|insufficient information)\b"
        ]

        hedges_found = 0
        for pattern in hedging_patterns:
            matches = re.findall(pattern, content.lower())
            if matches:
                hedges_found += len(matches)

        # Reduce confidence based on hedging occurrences
        if hedges_found > 0:
            reduction = min(0.40, hedges_found * 0.10)
            score = max(0.10, score - reduction)
            logger.info(f"Hedging detected ({hedges_found} instances). Calibrating confidence score down to {score:.2f}")

        # Check for citation anchors: responses with references have higher grounding proof
        citation_matches = re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", content)
        if citation_matches:
            # Anchor reward up to max 0.98
            score = min(0.98, score + 0.05)

        # Build execution trace summary mapping L6 steps
        trace = (
            f"LLM gateway finished completion generation. "
            f"Initial provider rating: {provider_score:.2f}. "
            f"Hedging adjustment triggers: -{hedges_found * 10}%. "
            f"Citation anchors reward: +{5 if citation_matches else 0}%. "
            f"Final calibrated confidence: {score:.2f}."
        )

        return score, trace
