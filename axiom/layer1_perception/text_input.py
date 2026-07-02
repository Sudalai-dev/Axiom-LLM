"""
OCIF Text Normalization & Security Screening — Layer 1.

Performs string sanitization, encoding validation, and prompt injection screening
(jailbreaks, rules overrides) (per Doc 14 Section 5).

Traces to:
  - Document 14 (Security Design) Section 5: AI-Specific Security (Jailbreak attempts)
  - Document 7 (LLD) Section 2: Perception Layer (Screening logic)
"""

import logging
import re
from typing import Tuple, List

logger = logging.getLogger("AxiomTextPerception")


class TextInputProcessor:
    """
    Sanitizes text strings and screens for prompt injection payloads.
    """

    # Adversarial patterns matching jailbreak attempts
    JAILBREAK_PATTERNS = [
        r"\b(ignore|bypass|override|disregard)\b.*\b(previous|system|instruction|rules)\b",
        r"\b(you are now|acting as|hypothetically|developer mode|dan)\b",
        r"\b(do not comply|ignore restrictions|disable safety)\b",
        r"\b(drop table|delete from|format c:)\b",  # Basic SQL Injection screening
    ]

    def process_text(self, text: str) -> Tuple[str, bool, List[str]]:
        """
        Sanitizes encoding, strips tags, and screens for safety violations.
        
        Returns: (sanitized_text, is_safe, detected_flags)
        """
        if not text:
            return "", True, []

        # 1. Clean control characters and trim
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()

        # 2. Check encoding bounds
        try:
            sanitized.encode("utf-8")
        except UnicodeEncodeError:
            logger.warning("Input contains invalid characters. Stripping non-UTF8 parts.")
            sanitized = sanitized.encode("utf-8", "ignore").decode("utf-8")

        # 3. Security Screening: prompt injection and SQL injection patterns
        detected_flags = []
        is_safe = True

        for idx, pattern in enumerate(self.JAILBREAK_PATTERNS):
            if re.search(pattern, sanitized, re.IGNORECASE):
                flag = f"injection_pattern_{idx+1}"
                detected_flags.append(flag)
                is_safe = False
                logger.warning(f"Security Alert: query triggered injection safety filter logic: '{flag}'")

        return sanitized, is_safe, detected_flags
