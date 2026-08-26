"""The only file in this project that touches a provider SDK.

One function, ``complete``. If we change provider or model, this file changes
and nothing else does.

Responses are cached on disk by prompt hash when INTEGRITY_LLM_CACHE_DIR is
set. That is what makes fixture runs repeatable and free while iterating on
false-positive suppression -- without it, every run of the fixture suite costs
money and gives slightly different answers, which makes it impossible to tell
whether a prompt edit helped.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

# Opus 5 runs adaptive thinking by default and rejects temperature outright, so
# there is no sampling knob to pin here. Determinism comes from the cache.

_client = None


class LLMUnavailable(RuntimeError):
    """No provider is configured, so contradiction analysis cannot run."""


def _cache_path(key: str) -> Optional[str]:
    directory = os.environ.get("INTEGRITY_LLM_CACHE_DIR")
    if not directory:
        return None
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{key}.json")


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise LLMUnavailable(
            "the anthropic package is not installed; run "
            "pip install anthropic (Phase 1 has no such dependency)"
        ) from exc
    try:
        _client = anthropic.Anthropic()
    except Exception as exc:
        raise LLMUnavailable(f"could not construct an Anthropic client: {exc}") from exc
    return _client


def complete(prompt: str, schema: Optional[dict[str, Any]] = None) -> str:
    """Send one prompt, return the model's text.

    ``schema`` constrains the reply to valid JSON matching that JSON Schema.
    Callers still validate what comes back -- a schema guarantees shape, not
    that the quotes inside it are real, which is what the verbatim check is
    for.
    """
    key = hashlib.sha256(
        json.dumps({"model": MODEL, "prompt": prompt, "schema": schema}, sort_keys=True).encode()
    ).hexdigest()[:32]

    path = _cache_path(key)
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)["response"]

    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        # Server-side refusal fallback: a safety classifier declining a
        # transcript would otherwise return stop_reason "refusal" with no
        # content, silently producing an empty contradiction list.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

    response = client.beta.messages.create(**kwargs)

    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        raise LLMUnavailable(f"request was refused by a safety classifier: {details}")

    text = next((b.text for b in response.content if b.type == "text"), "")

    if path:
        with open(path, "w") as f:
            json.dump({"prompt": prompt, "response": text}, f, indent=2)
    return text
