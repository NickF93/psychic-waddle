"""Explicit runtime configuration for provider selection."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlparse

from portfolio_rag_assistant.provider import LLMProviderConfigurationError

LLMBackend = Literal["ollama", "llama-cpp", "openai-compatible"]

SUPPORTED_LLM_BACKENDS: frozenset[str] = frozenset(
    ("ollama", "llama-cpp", "openai-compatible")
)


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """Validated model provider settings."""

    backend: LLMBackend
    base_url: str
    chat_model: str
    embedding_model: str
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.backend not in SUPPORTED_LLM_BACKENDS:
            allowed = ", ".join(sorted(SUPPORTED_LLM_BACKENDS))
            raise LLMProviderConfigurationError(
                f"LLM_BACKEND must be one of: {allowed}"
            )

        base_url = _normalize_base_url(self.base_url)
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "chat_model", _require_text(self.chat_model, "CHAT_MODEL"))
        object.__setattr__(
            self,
            "embedding_model",
            _require_text(self.embedding_model, "EMBEDDING_MODEL"),
        )
        if self.api_key is not None:
            api_key = self.api_key.strip()
            object.__setattr__(self, "api_key", api_key or None)


def load_provider_settings(env: Mapping[str, str] | None = None) -> ProviderSettings:
    """Load provider settings from exact environment variable names."""

    source = os.environ if env is None else env
    backend = _require_text(source.get("LLM_BACKEND"), "LLM_BACKEND")

    return ProviderSettings(
        backend=cast(LLMBackend, backend),
        base_url=_require_text(source.get("LLM_BASE_URL"), "LLM_BASE_URL"),
        chat_model=_require_text(source.get("CHAT_MODEL"), "CHAT_MODEL"),
        embedding_model=_require_text(
            source.get("EMBEDDING_MODEL"),
            "EMBEDDING_MODEL",
        ),
        api_key=source.get("LLM_API_KEY"),
    )


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise LLMProviderConfigurationError(f"{field_name} must be set")
    return value.strip()


def _normalize_base_url(value: str) -> str:
    base_url = _require_text(value, "LLM_BASE_URL").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LLMProviderConfigurationError(
            "LLM_BASE_URL must be an absolute http or https API root"
        )
    return base_url
