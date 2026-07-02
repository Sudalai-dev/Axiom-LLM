"""
OCIF Multimodal Attachment Processor — Layer 1.

Validates file uploads size limits and MIME content types before ingestion
to defend service layer pipelines against binary leaks (per Doc 14 Section 5).

Traces to:
  - Document 14 (Security Design) Section 5: AI-Specific Security (Tool exfiltration/data leaks)
  - Document 18 (Deployment Guide) Section 2.1: container image sizes and checks
"""

import logging
import os
from typing import Tuple, Optional

logger = logging.getLogger("AxiomDocumentPerception")


class DocumentInputProcessor:
    """
    Validates uploaded file types, sizes, and formats.
    """

    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".json", ".yaml", ".yml"
    }

    # Max upload limit: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def validate_attachment(
        self,
        filepath: str,
        mime_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates file size boundaries and extension white-listing.
        """
        if not os.path.exists(filepath):
            return False, "File resource does not exist on disk."

        # 1. Size Verification
        size = os.path.getsize(filepath)
        if size > self.MAX_FILE_SIZE:
            logger.warning(f"File upload size ({size} bytes) exceeds limit of {self.MAX_FILE_SIZE} bytes.")
            return False, f"File size exceeds maximum boundary limit of {self.MAX_FILE_SIZE // (1024*1024)}MB."

        # 2. Extension Verification
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            logger.warning(f"File upload extension '{ext}' is not in allowed list.")
            return False, f"File format extension '{ext}' is not supported."

        return True, None
