"""Test-suite guards.

The local LLM is an OPT-IN runtime enhancement (OCIF_LLM_ENABLED=true in a
developer's .env). The test suite, however, must stay deterministic and
offline: it must never make real calls to a locally-running Ollama, whose
output is non-deterministic and whose availability varies by machine/CI. Tests
that want to exercise the LLM path inject a fake client explicitly
(see tests/test_local_llm.py).

Setting the env var here — at conftest import, before core.config is first
imported — means load_dotenv() (which does NOT override existing env vars) can't
re-enable it from .env. We also defensively force the settings singleton off in
case config was already imported by a plugin.
"""

import os

os.environ["OCIF_LLM_ENABLED"] = "false"

try:  # defensive: neutralize an already-constructed settings singleton
    from dataclasses import replace

    from core.config import settings

    if getattr(settings, "llm", None) is not None and settings.llm.enabled:
        settings.llm = replace(settings.llm, enabled=False)
except Exception:  # noqa: BLE001 — never let the guard break collection
    pass
