"""
Perception Engine (Engine 1) — environment analysis + input normalization.

Normalizes all inbound signal (text, documents, code, config, logs) into a
canonical PerceptionFrame and performs the mandatory ingress safety screen.
"""

import re

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    EngineStatus,
    PerceptionFrame,
)

# Ingress screening — prompt-injection / unsafe control phrases
_UNSAFE_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"disregard\s+(your\s+)?guardrails",
]

_CODE_HINTS = re.compile(
    r"```|def\s+\w+\(|class\s+\w+[:(]|import\s+\w+|SELECT\s+.+\s+FROM|curl\s+-|docker\s+run",
    re.IGNORECASE,
)
_CONFIG_HINTS = re.compile(r"\.ya?ml|\.json\b|\.env\b|\.toml\b|Dockerfile|docker-compose", re.IGNORECASE)
_LOG_HINTS = re.compile(r"\b(ERROR|WARN|Traceback|stack\s*trace|exception in)\b")


class PerceptionEngine(CognitiveEngine):
    name = EngineName.PERCEPTION

    async def _run(self, context: CognitiveContext) -> EngineResult:
        raw = context.task or ""
        normalized = re.sub(r"[ \t]+", " ", raw.replace("\r\n", "\n")).strip()

        input_kinds = ["text"]
        if _CODE_HINTS.search(normalized):
            input_kinds.append("code")
        if _CONFIG_HINTS.search(normalized):
            input_kinds.append("config")
        if _LOG_HINTS.search(normalized):
            input_kinds.append("log")

        attachments = context.metadata.get("attachments", [])
        if attachments:
            input_kinds.append("document")

        is_safe = True
        rejection_reason = None
        lowered = normalized.lower()
        for pattern in _UNSAFE_PATTERNS:
            if re.search(pattern, lowered):
                is_safe = False
                rejection_reason = "Input rejected by ingress safety screening."
                break

        context.perception = PerceptionFrame(
            raw_text=raw,
            normalized_text=normalized,
            input_kinds=input_kinds,
            attachments=attachments,
            environment={
                "tenant_id": context.tenant_id,
                "project": context.project,
                "conversation_id": context.conversation_id,
                "has_attachments": bool(attachments),
            },
            is_safe=is_safe,
            rejection_reason=rejection_reason,
        )

        return EngineResult(
            engine=self.name,
            status=EngineStatus.COMPLETED if is_safe else EngineStatus.FAILED,
            summary=(
                f"Normalized input ({', '.join(input_kinds)}); safety screen "
                f"{'passed' if is_safe else 'BLOCKED'}."
            ),
            payload={"input_kinds": input_kinds, "is_safe": is_safe},
        )
