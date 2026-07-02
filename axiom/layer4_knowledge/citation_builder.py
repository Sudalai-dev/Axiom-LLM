"""
OCIF Citation Builder — Layer 4.

Maps raw search outcomes to canonical GroundedChunk models. Ensures all citations
are fully traceable, verified, and mapped per the required output schemas.

Traces to:
  - Document 11 (RAG Design) Section 5: Citation Attachment
  - Document 7 (LLD) Section 5: Knowledge Layer contract
"""

import logging
from typing import List, Dict, Any

from axiom.core.models.base import SourceType
from axiom.core.models.knowledge import GroundedChunk

logger = logging.getLogger("AxiomCitationBuilder")


class CitationBuilder:
    """
    Enforces DTO contract mapping for retrieved grounding citations.
    """

    def build_citations(self, fused_results: List[Dict[str, Any]]) -> List[GroundedChunk]:
        """
        Converts fused search result dictionary logs into verified Pydantic GroundedChunk items.
        """
        grounded_chunks = []
        for idx, res in enumerate(fused_results):
            chunk_id = res["id"]
            doc_id = res["doc_id"]
            title = res["title"]
            text_content = res["text"]
            score = res["rrf_score"]
            section_ref = res.get("section_ref", "General")
            
            # Map source type string safely to enum
            source_str = res.get("source_type", "upload").lower()
            try:
                source_type = SourceType(source_str)
            except ValueError:
                source_type = SourceType.UPLOAD

            grounded_chunks.append(
                GroundedChunk(
                    chunk_id=str(chunk_id),
                    doc_id=str(doc_id),
                    title=str(title),
                    section_ref=str(section_ref),
                    text=str(text_content),
                    score=float(score),
                    source_type=source_type,
                    metadata=res.get("metadata", {})
                )
            )

        logger.debug(f"Assembled {len(grounded_chunks)} verified GroundedChunk citations.")
        return grounded_chunks
