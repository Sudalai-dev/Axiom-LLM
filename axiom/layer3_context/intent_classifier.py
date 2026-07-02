"""
OCIF Intent Classifier — Layer 3.

Classifies incoming user queries into semantic intents (CodeGen, ArchitectureReview,
GeneralQ&A, etc.). If classification confidence is low (< 0.70), flags the context
for user clarification rather than guessing (per Doc 7 Section 4).

Traces to:
  - Document 6 (LLD) Section 3.1: Context Intelligence Components
  - Document 7 (LLD) Section 4: Context Layer contract (Failure Modes)
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger("AxiomIntentClassifier")


class IntentClassifier:
    """
    Evaluates incoming request texts to resolve semantic intent boundaries.
    """

    INTENT_PATTERNS = {
        "CodeGen": [
            r"\b(code|function|class|fastapi|python|generate|write|implement|script|program)\b",
            r"\b(api|endpoint|route|json|schema|pydantic|controller)\b",
        ],
        "ArchitectureReview": [
            r"\b(architecture|design|db|schema|structure|layers|blueprint|hld|lld|ocif)\b",
            r"\b(flow|diagram|relationship|component|model|pipeline|topology)\b",
        ],
        "SystemAdmin": [
            r"\b(register|tool|policy|user|tenant|config|permissions|restrict|allow)\b",
            r"\b(rbac|assign|role|onboard|threshold|limit|throttle)\b",
        ]
    }

    def classify(self, query: str) -> Tuple[str, float, bool]:
        """
        Runs regex-based semantic analysis.
        Returns: (intent_name, confidence_score, requires_clarification)
        """
        query_clean = query.strip().lower()
        if not query_clean:
            return "GeneralQ&A", 1.0, False

        intent_scores = {}
        for intent, patterns in self.INTENT_PATTERNS.items():
            matches = 0
            for pattern in patterns:
                matches += len(re.findall(pattern, query_clean))
            if matches > 0:
                intent_scores[intent] = matches

        if not intent_scores:
            # General conversation or low-match query
            return "GeneralQ&A", 0.85, False

        # Find the highest scoring intent
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_score = sorted_intents[0]

        # Calculate a mock confidence score based on relative weight
        total_score = sum(intent_scores.values())
        confidence = float(top_score / total_score)

        # Apply the confidence threshold rule per Doc 7 Section 4
        # If there's an exact equal tie or confidence is low, require clarification
        requires_clarification = False
        if len(sorted_intents) > 1 and sorted_intents[0][1] == sorted_intents[1][1]:
            # Tie between intents
            requires_clarification = True
            confidence = 0.50
        elif confidence < 0.70:
            requires_clarification = True

        logger.debug(
            f"Classified intent: '{top_intent}' with confidence {confidence:.2f}. "
            f"Requires clarification: {requires_clarification}"
        )
        return top_intent, confidence, requires_clarification
