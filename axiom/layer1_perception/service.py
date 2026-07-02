"""
OCIF Perception Service Wrapper — Layer 1.

Sanitizes text queries, screens for prompt injections, validates file size/type
upload limits, and constructs the canonical PerceptionEvent contract (per Doc 7 Section 2).

Traces to:
  - Document 7 (LLD) Section 2: Perception Layer contract
  - Document 14 (Security Design) Section 5: AI-Specific Security (Prompt injection mitigation)
"""

import logging
from typing import List, Dict, Any, Optional

from axiom.core.models.perception import PerceptionEvent, InputAttachment
from axiom.layer1_perception.text_input import TextInputProcessor
from axiom.layer1_perception.document_input import DocumentInputProcessor

logger = logging.getLogger("AxiomPerceptionService")


class PerceptionService:
    """
    Unified entrypoint for the Layer 1 Perception Service.
    """

    def __init__(self) -> None:
        self.text_processor = TextInputProcessor()
        self.doc_processor = DocumentInputProcessor()

    async def process_input(
        self,
        query: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        source_channel: str = "chat",
        client_metadata: Optional[Dict[str, Any]] = None
    ) -> PerceptionEvent:
        """
        Processes query and attachment structures.
        """
        logger.info(f"Ingesting raw input from channel '{source_channel}'")

        # 1. Process and screen text
        sanitized_text, is_safe, security_flags = self.text_processor.process_text(query)

        # 2. Process and validate attachments
        parsed_attachments = []
        rejection_reason = None
        
        if attachments:
            for att in attachments:
                filepath = att.get("uri")
                mime_type = att.get("type")
                
                # Run validation checks
                ok, err = self.doc_processor.validate_attachment(filepath, mime_type)
                if not ok:
                    is_safe = False
                    rejection_reason = err
                    break
                    
                parsed_attachments.append(
                    InputAttachment(
                        type=att.get("type", "document"),
                        uri=filepath,
                        mime_type=att.get("mime_type"),
                        size_bytes=att.get("size")
                    )
                )

        if security_flags and not rejection_reason:
            rejection_reason = "Prompt injection pattern or SQL injection payload flagged during input screening."

        # Estimate token length (crude approximation: characters / 4)
        token_count = len(sanitized_text) // 4

        # 3. Assemble and return PerceptionEvent
        event = PerceptionEvent(
            raw_text=sanitized_text,
            input_type="document" if parsed_attachments else "text",
            attachments=parsed_attachments,
            language_detected="en",  # Default
            encoding_valid=True,
            input_length_tokens=token_count,
            security_flags=security_flags,
            is_safe=is_safe,
            rejection_reason=rejection_reason,
            source_channel=source_channel,
            client_metadata=client_metadata or {}
        )

        logger.info(f"Assembled PerceptionEvent '{event.event_id}'. is_safe: {event.is_safe}")
        return event
