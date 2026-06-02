"""Explicit runtime configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlparse

from portfolio_rag_assistant.provider import (
    ChatProvider,
    EmbeddingProvider,
    LLMProviderConfigurationError,
    LlamaCppProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from portfolio_rag_assistant.retrieval import RetrievalConfigurationError

ProviderBackend = Literal["ollama", "llama-cpp", "openai-compatible"]

SUPPORTED_PROVIDER_BACKENDS: frozenset[str] = frozenset(
    ("ollama", "llama-cpp", "openai-compatible")
)


class RuntimeConfigurationError(RuntimeError):
    """Raised when non-provider runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ChatProviderSettings:
    """Validated chat model provider settings."""

    backend: ProviderBackend
    base_url: str
    model: str
    api_key: str | None = None

    def __post_init__(self) -> None:
        _require_supported_backend(self.backend, "CHAT_BACKEND")
        object.__setattr__(
            self,
            "base_url",
            _normalize_base_url(self.base_url, "CHAT_BASE_URL"),
        )
        object.__setattr__(self, "model", _require_text(self.model, "CHAT_MODEL"))
        object.__setattr__(self, "api_key", _normalize_api_key(self.api_key))


@dataclass(frozen=True, slots=True)
class EmbeddingProviderSettings:
    """Validated embedding model provider settings."""

    backend: ProviderBackend
    base_url: str
    model: str
    api_key: str | None = None

    def __post_init__(self) -> None:
        _require_supported_backend(self.backend, "EMBEDDING_BACKEND")
        object.__setattr__(
            self,
            "base_url",
            _normalize_base_url(self.base_url, "EMBEDDING_BASE_URL"),
        )
        object.__setattr__(
            self,
            "model",
            _require_text(self.model, "EMBEDDING_MODEL"),
        )
        object.__setattr__(self, "api_key", _normalize_api_key(self.api_key))


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Validated PostgreSQL connection settings."""

    host: str
    port: int
    name: str
    user: str
    password: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "host",
            _require_runtime_text(self.host, "DB_HOST"),
        )
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise RuntimeConfigurationError("DB_PORT must be an integer")
        if not 1 <= self.port <= 65535:
            raise RuntimeConfigurationError("DB_PORT must be between 1 and 65535")
        object.__setattr__(self, "name", _require_runtime_text(self.name, "DB_NAME"))
        object.__setattr__(self, "user", _require_runtime_text(self.user, "DB_USER"))
        object.__setattr__(
            self,
            "password",
            _require_runtime_text(self.password, "DB_PASSWORD"),
        )


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Validated retrieval settings."""

    top_k: int
    min_score: float

    def __post_init__(self) -> None:
        if not isinstance(self.top_k, int) or isinstance(self.top_k, bool):
            raise RetrievalConfigurationError("RETRIEVAL_TOP_K must be an integer")
        if self.top_k <= 0:
            raise RetrievalConfigurationError("RETRIEVAL_TOP_K must be positive")
        if not isinstance(self.min_score, float):
            raise RetrievalConfigurationError("RETRIEVAL_MIN_SCORE must be a float")
        if not 0 <= self.min_score <= 1:
            raise RetrievalConfigurationError(
                "RETRIEVAL_MIN_SCORE must be between 0 and 1"
            )


@dataclass(frozen=True, slots=True)
class QuestionCollectionSettings:
    """Validated anonymous question collection settings."""

    enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise RuntimeConfigurationError(
                "QUESTION_COLLECTION_ENABLED must be true or false"
            )


def load_chat_provider_settings(
    env: Mapping[str, str] | None = None,
) -> ChatProviderSettings:
    """Load chat provider settings from exact environment variable names."""

    source = os.environ if env is None else env
    backend = _require_text(source.get("CHAT_BACKEND"), "CHAT_BACKEND")

    return ChatProviderSettings(
        backend=cast(ProviderBackend, backend),
        base_url=_require_text(source.get("CHAT_BASE_URL"), "CHAT_BASE_URL"),
        model=_require_text(source.get("CHAT_MODEL"), "CHAT_MODEL"),
        api_key=source.get("CHAT_API_KEY"),
    )


def load_embedding_provider_settings(
    env: Mapping[str, str] | None = None,
) -> EmbeddingProviderSettings:
    """Load embedding provider settings from exact environment variable names."""

    source = os.environ if env is None else env
    backend = _require_text(source.get("EMBEDDING_BACKEND"), "EMBEDDING_BACKEND")

    return EmbeddingProviderSettings(
        backend=cast(ProviderBackend, backend),
        base_url=_require_text(
            source.get("EMBEDDING_BASE_URL"),
            "EMBEDDING_BASE_URL",
        ),
        model=_require_text(source.get("EMBEDDING_MODEL"), "EMBEDDING_MODEL"),
        api_key=source.get("EMBEDDING_API_KEY"),
    )


def load_database_settings(env: Mapping[str, str] | None = None) -> DatabaseSettings:
    """Load database settings from exact environment variable names."""

    source = os.environ if env is None else env
    return DatabaseSettings(
        host=_require_runtime_text(source.get("DB_HOST"), "DB_HOST"),
        port=_require_runtime_int(source.get("DB_PORT"), "DB_PORT"),
        name=_require_runtime_text(source.get("DB_NAME"), "DB_NAME"),
        user=_require_runtime_text(source.get("DB_USER"), "DB_USER"),
        password=_require_runtime_text(source.get("DB_PASSWORD"), "DB_PASSWORD"),
    )


def load_retrieval_settings(env: Mapping[str, str] | None = None) -> RetrievalSettings:
    """Load retrieval settings from exact environment variable names."""

    source = os.environ if env is None else env
    return RetrievalSettings(
        top_k=_require_retrieval_int(source.get("RETRIEVAL_TOP_K"), "RETRIEVAL_TOP_K"),
        min_score=_require_retrieval_float(
            source.get("RETRIEVAL_MIN_SCORE"),
            "RETRIEVAL_MIN_SCORE",
        ),
    )


def load_question_collection_settings(
    env: Mapping[str, str] | None = None,
) -> QuestionCollectionSettings:
    """Load question collection settings from exact environment variable names."""

    source = os.environ if env is None else env
    return QuestionCollectionSettings(
        enabled=_require_runtime_bool(
            source.get("QUESTION_COLLECTION_ENABLED"),
            "QUESTION_COLLECTION_ENABLED",
        )
    )


def build_chat_provider(settings: ChatProviderSettings) -> ChatProvider:
    """Build the configured chat provider."""

    provider = _build_provider(
        backend=settings.backend,
        base_url=settings.base_url,
        api_key=settings.api_key,
    )
    return cast(ChatProvider, provider)


def build_embedding_provider(
    settings: EmbeddingProviderSettings,
) -> EmbeddingProvider:
    """Build the configured embedding provider."""

    provider = _build_provider(
        backend=settings.backend,
        base_url=settings.base_url,
        api_key=settings.api_key,
    )
    return cast(EmbeddingProvider, provider)


def _build_provider(
    *,
    backend: ProviderBackend,
    base_url: str,
    api_key: str | None,
) -> object:
    if backend == "ollama":
        return OllamaProvider(base_url=base_url, api_key=api_key)
    if backend == "llama-cpp":
        return LlamaCppProvider(base_url=base_url, api_key=api_key)
    if backend == "openai-compatible":
        return OpenAICompatibleProvider(base_url=base_url, api_key=api_key)
    raise LLMProviderConfigurationError("unsupported provider backend")


def _require_supported_backend(value: str, field_name: str) -> None:
    if value not in SUPPORTED_PROVIDER_BACKENDS:
        allowed = ", ".join(sorted(SUPPORTED_PROVIDER_BACKENDS))
        raise LLMProviderConfigurationError(f"{field_name} must be one of: {allowed}")


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise LLMProviderConfigurationError(f"{field_name} must be set")
    return value.strip()


def _normalize_base_url(value: str, field_name: str) -> str:
    base_url = _require_text(value, field_name).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LLMProviderConfigurationError(
            f"{field_name} must be an absolute http or https API root"
        )
    return base_url


def _normalize_api_key(value: str | None) -> str | None:
    if value is None:
        return None
    api_key = value.strip()
    return api_key or None


def _require_runtime_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise RuntimeConfigurationError(f"{field_name} must be set")
    return value.strip()


def _require_runtime_int(value: str | None, field_name: str) -> int:
    text = _require_runtime_text(value, field_name)
    try:
        return int(text)
    except ValueError as exc:
        raise RuntimeConfigurationError(f"{field_name} must be an integer") from exc


def _require_runtime_bool(value: str | None, field_name: str) -> bool:
    text = _require_runtime_text(value, field_name).lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise RuntimeConfigurationError(f"{field_name} must be true or false")


def _require_retrieval_int(value: str | None, field_name: str) -> int:
    text = _require_retrieval_text(value, field_name)
    try:
        return int(text)
    except ValueError as exc:
        raise RetrievalConfigurationError(f"{field_name} must be an integer") from exc


def _require_retrieval_float(value: str | None, field_name: str) -> float:
    text = _require_retrieval_text(value, field_name)
    try:
        return float(text)
    except ValueError as exc:
        raise RetrievalConfigurationError(f"{field_name} must be a float") from exc


def _require_retrieval_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise RetrievalConfigurationError(f"{field_name} must be set")
    return value.strip()
