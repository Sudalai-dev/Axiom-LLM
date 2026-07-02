"""
OCIF Hallucination Detector — Layer 7 (META CORE).

Cross-checks model outputs against grounding documents to detect hallucinated entities
and facts. Enforces confidence score limits and source correlation (per Doc 7 Section 8).

Traces to:
  - Document 7 (LLD) Section 8: Decision & Action Layer (Hallucination detection)
  - Document 11 (RAG Design) Section 4.3: No-grounding response validation
"""

import logging
import re
from typing import List, Tuple, Optional

from axiom.core.models.knowledge import GroundedChunk


logger = logging.getLogger("AxiomHallucinationDetector")


class HallucinationDetector:
    """
    Validates output text semantic grounding alignment.
    """

    def verify_grounding(
        self,
        content: str,
        grounding_chunks: List[GroundedChunk],
        no_grounding_found: bool
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Runs factual overlap scans. Checks if entities (numbers, capitalized nouns, etc.)
        asserted in response content are grounded in chunks text.
        
        Returns: (is_grounded, grounding_score, error_message)
        """
        # If Layer 4 reported no grounding chunks were found, but the model generated
        # a response containing factual assertions, it must be flagged (Doc 11 Section 4.3)
        if no_grounding_found:
            # Check if response discloses the absence of grounding
            disclosure_keywords = ["no information", "cannot find", "not grounded", "not found", "no grounding"]
            if any(k in content.lower() for k in disclosure_keywords):
                logger.info("No grounding found; model response successfully disclosed absence of grounding.")
                return True, 1.0, None
            else:
                logger.warning("Factual response generated when no grounding chunks exist in memory index!")
                return False, 0.0, "Hallucination: response contains assertions but no grounding documents exist."

        if not grounding_chunks:
            return True, 1.0, None

        # Combine all grounding texts
        combined_grounding = " ".join(chunk.text.lower() for chunk in grounding_chunks)

        # Extract numeric entities, symbols, or codes (e.g. #4471, $240.00, IP, port)
        # as these are high-risk targets for hallucination (ungrounded transactions, etc.)
        entities = re.findall(r"\b\d+(?:\.\d+)?\b|\b[A-Za-z0-9_\-\.\#]+\b", content)
        # Filter down to entities containing numbers or uppercase letters
        critical_entities = [
            e for e in entities 
            if re.search(r"\d", e) or (len(e) >= 3 and e.isupper())
        ]

        if not critical_entities:
            # Simple text query: default pass
            return True, 0.95, None

        matches = 0
        missing_entities = []
        for entity in set(critical_entities):
            if entity.lower() in combined_grounding:
                matches += 1
            else:
                missing_entities.append(entity)

        grounding_score = float(matches / len(set(critical_entities)))
        logger.info(f"Factual grounding score: {grounding_score:.2f} ({matches}/{len(set(critical_entities))} entities found)")

        # Threshold limit rule: if grounding falls below 80% of critical entities, flag
        if grounding_score < 0.80:
            logger.warning(f"Grounding score {grounding_score:.2f} is below 80% threshold. Missing terms: {missing_entities}")
            return False, grounding_score, f"Hallucination Warning: response contains ungrounded technical parameters/values: {missing_entities}"

        return True, grounding_score, None

