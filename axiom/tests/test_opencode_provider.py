"""OpenCode provider tests — response parsing and graceful degradation.

These do not require a running OpenCode server: parsing is tested against a
captured real response shape, and the offline path is asserted to degrade to a
``*-simulated`` payload (which the InferenceAdapter maps to the synthesizer).
"""

import asyncio

from inference.providers.opencode_provider import OpenCodeProvider


def test_parse_completion_extracts_text_and_tokens():
    provider = OpenCodeProvider()
    # Shape captured from a real `opencode serve` assistant message.
    messages = [
        {
            "type": "assistant",
            "model": {"id": "deepseek-v4-flash-free", "providerID": "opencode"},
            "content": [
                {"type": "reasoning", "text": "thinking..."},
                {"type": "text", "text": "MQTT is a lightweight pub/sub protocol."},
            ],
            "cost": 0,
            "tokens": {"input": 3178, "output": 19},
        },
        {"type": "user", "content": [{"type": "text", "text": "what is MQTT?"}]},
    ]
    result = provider._parse_completion(messages)
    assert result["content"] == "MQTT is a lightweight pub/sub protocol."
    assert result["model_used"] == "opencode/deepseek-v4-flash-free"
    assert result["tokens_used"]["input"] == 3178
    assert result["tokens_used"]["cost_usd"] == 0.0
    assert not result["model_used"].endswith("-simulated")


def test_generate_degrades_when_disabled():
    provider = OpenCodeProvider()
    provider.enabled = False
    payload = asyncio.run(provider.generate("hello", max_tokens=100, temperature=0.3))
    # Degraded output is flagged simulated so the adapter uses the synthesizer.
    assert payload["model_used"].endswith("-simulated")


def test_generate_degrades_when_server_unreachable():
    provider = OpenCodeProvider()
    provider.enabled = True
    provider.base_url = "http://127.0.0.1:59999"  # nothing listening
    provider.timeout = 2
    payload = asyncio.run(provider.generate("hello", max_tokens=100, temperature=0.3))
    assert payload["model_used"].endswith("-simulated")


def test_model_ref_splits_provider_and_id():
    provider = OpenCodeProvider("opencode/hy3-free")
    assert provider._model_ref() == {"providerID": "opencode", "id": "hy3-free"}
