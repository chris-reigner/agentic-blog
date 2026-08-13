"""LLM client seam — one place that talks to an OpenAI-compatible endpoint.

Works with OpenRouter, Ollama, llama.cpp, or the OpenAI API. Every distiller
node depends on the :class:`LLMClient` Protocol, so tests inject a fake and the
real client (backed by ``openai``) is imported lazily.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from agentic_blog.settings import LLMSettings

logger = logging.getLogger(__name__)

# How many times to re-request when a model returns an empty content channel.
_EMPTY_RETRIES = 3


@runtime_checkable
class LLMClient(Protocol):
    """Minimal chat surface the distill silo needs."""

    def complete(self, system: str, user: str, *, temperature: float | None = None) -> str:
        """Return the assistant's text for a system+user turn."""
        ...


class OpenAICompatibleClient:
    """Real client backed by the ``openai`` SDK (OpenRouter by default)."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
            raise RuntimeError("openai is required for the real LLM client.") from exc
        headers: dict[str, str] | None = None
        if "openrouter.ai" in self._settings.base_url:
            headers = {
                "HTTP-Referer": self._settings.openrouter_site_url,
                "X-Title": self._settings.openrouter_app_name,
            }
        api_key = self._settings.api_key
        if not api_key:
            # Local backends (Ollama, llama.cpp) ignore the key, but the OpenAI
            # SDK requires a non-empty string. Only remote endpoints need a real one.
            if self._is_local(self._settings.base_url):
                api_key = "not-needed"
            else:
                raise RuntimeError("LLM_API_KEY is not set (put it in .env).")
        self._client = OpenAI(
            base_url=self._settings.base_url,
            api_key=api_key,
            default_headers=headers,
            timeout=self._settings.timeout_seconds,
        )
        return self._client

    @staticmethod
    def _is_local(base_url: str) -> bool:
        return any(host in base_url for host in ("localhost", "127.0.0.1", "0.0.0.0"))

    def complete(self, system: str, user: str, *, temperature: float | None = None) -> str:
        client = self._ensure_client()
        temp = self._settings.temperature if temperature is None else temperature
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        # Every prompt in this app asks for strict JSON, so constrain the output
        # to a JSON object. This keeps flaky/reasoning models (e.g. gpt-oss on
        # Ollama) from emitting prose or an empty content channel. Backends that
        # reject the parameter fall back to unconstrained decoding.
        kwargs: dict[str, Any] = {
            "model": self._settings.model,
            "temperature": temp,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(_EMPTY_RETRIES):
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                if "response_format" in kwargs and self._is_response_format_error(exc):
                    logger.info("Backend rejected response_format; retrying without it.")
                    kwargs.pop("response_format")
                    continue
                raise
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
            logger.warning("LLM returned empty content (attempt %d); retrying.", attempt + 1)
        return ""

    @staticmethod
    def _is_response_format_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "response_format" in text or "response format" in text


def extract_json(text: str) -> Any:
    """Best-effort parse of a JSON object/array from an LLM response.

    Tolerates ```json fences and leading/trailing prose by slicing to the first
    balanced ``{...}`` or ``[...]`` span.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```", 2)[1] if "```" in stripped[3:] else stripped
        stripped = stripped.removeprefix("json").strip().strip("`").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("No parseable JSON found in LLM response.")
