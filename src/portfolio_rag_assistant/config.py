"""Explicit runtime configuration."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast
from urllib.parse import urlparse
from portfolio_rag_assistant.provider.parameters import (
    ParameterProfile,
    DEFAULT_PROFILES,
)
from portfolio_rag_assistant.provider.budget import InputBudget
from portfolio_rag_assistant.provider.contract import ChatRequest, ChatMessage

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
    timeout_seconds: float = 30.0
    max_tokens: int = 384
    temperature: float | None = None
    top_p: float | None = None
    reasoning_mode: str = "default"
    reasoning_effort: str | None = None
    profile_name: str | None = None
    profiles_path: str = str(DEFAULT_PROFILES)
    input_budget: InputBudget = field(default_factory=InputBudget)

    @property
    def request_options(self):
        return dict(
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            reasoning_mode=self.reasoning_mode,
            reasoning_effort=self.reasoning_effort,
        )

    @property
    def parameter_profile(self):
        return ParameterProfile.load(
            self.profile_name or ("ollama" if self.backend == "ollama" else "openai"),
            self.profiles_path,
        )

    def __post_init__(self) -> None:
        _require_supported_backend(self.backend, "CHAT_BACKEND")
        try:
            sample = ChatRequest(
                model=self.model,
                messages=(ChatMessage("user", "validation"),),
                **self.request_options,
            )
            self.parameter_profile.encode(sample)
        except (ValueError, TypeError) as error:
            raise LLMProviderConfigurationError(
                "invalid normalized generation settings"
            ) from error
        if (
            self.input_budget.context_tokens is not None
            and self.max_tokens + self.input_budget.framing_reserve
            >= self.input_budget.context_tokens
        ):
            raise LLMProviderConfigurationError(
                "generation reservation exhausts target context"
            )
        object.__setattr__(
            self,
            "base_url",
            _normalize_base_url(self.base_url, "CHAT_BASE_URL"),
        )
        object.__setattr__(self, "model", _require_text(self.model, "CHAT_MODEL"))
        object.__setattr__(self, "api_key", _normalize_api_key(self.api_key))
        if (
            isinstance(self.max_tokens, bool)
            or not isinstance(self.max_tokens, int)
            or self.max_tokens <= 0
        ):
            raise LLMProviderConfigurationError(
                "CHAT_MAX_TOKENS must be a positive integer"
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise LLMProviderConfigurationError(
                "CHAT_TIMEOUT_SECONDS must be a finite positive number"
            )


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
    candidate_fan_out: int
    min_score: float

    def __post_init__(self) -> None:
        if not isinstance(self.top_k, int) or isinstance(self.top_k, bool):
            raise RetrievalConfigurationError("RETRIEVAL_TOP_K must be an integer")
        if self.top_k <= 0:
            raise RetrievalConfigurationError("RETRIEVAL_TOP_K must be positive")
        if not isinstance(self.candidate_fan_out, int) or isinstance(
            self.candidate_fan_out,
            bool,
        ):
            raise RetrievalConfigurationError(
                "RETRIEVAL_CANDIDATE_FAN_OUT must be an integer"
            )
        if self.candidate_fan_out <= 0:
            raise RetrievalConfigurationError(
                "RETRIEVAL_CANDIDATE_FAN_OUT must be positive"
            )
        if self.candidate_fan_out < self.top_k:
            raise RetrievalConfigurationError(
                "RETRIEVAL_CANDIDATE_FAN_OUT must be at least RETRIEVAL_TOP_K"
            )
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


@dataclass(frozen=True, slots=True)
class IntentCatalogSettings:
    """Validated intent catalog settings."""

    path: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "path",
            _require_runtime_text(self.path, "INTENT_PROFILES_PATH"),
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
        timeout_seconds=_require_chat_timeout(source.get("CHAT_TIMEOUT_SECONDS", "30")),
        max_tokens=_require_chat_max_tokens(source.get("CHAT_MAX_TOKENS", "384")),
        temperature=_optional_float(source.get("CHAT_TEMPERATURE")),
        top_p=_optional_float(source.get("CHAT_TOP_P")),
        reasoning_mode=source.get("CHAT_REASONING_MODE", "default"),
        reasoning_effort=source.get("CHAT_REASONING_EFFORT") or None,
        profile_name=source.get("CHAT_PARAMETER_PROFILE") or None,
        profiles_path=source.get("GENERATION_PROFILES_PATH") or str(DEFAULT_PROFILES),
        input_budget=InputBudget(
            max_bytes=_positive_int(source.get("CHAT_INPUT_MAX_BYTES", "65536")),
            context_tokens=_positive_int(source["CHAT_CONTEXT_TOKENS"])
            if source.get("CHAT_CONTEXT_TOKENS")
            else None,
            tokenizer_path=source.get("CHAT_INPUT_TOKENIZER") or None,
        ),
    )


def load_fallback_chat_provider_settings(
    env: Mapping[str, str],
) -> ChatProviderSettings | None:
    """Reuse validated provider settings for one explicitly configured fallback."""
    fields = (
        "BACKEND",
        "BASE_URL",
        "MODEL",
        "API_KEY",
        "TEMPERATURE",
        "TOP_P",
        "REASONING_MODE",
        "REASONING_EFFORT",
        "PARAMETER_PROFILE",
        "INPUT_MAX_BYTES",
        "CONTEXT_TOKENS",
        "INPUT_TOKENIZER",
    )
    if not any(env.get(f"CHAT_FALLBACK_{field}", "").strip() for field in fields[:4]):
        return None
    settings = {
        f"CHAT_{field}": env.get(f"CHAT_FALLBACK_{field}", "") for field in fields
    }
    settings["CHAT_TIMEOUT_SECONDS"] = env.get("CHAT_FALLBACK_TIMEOUT_SECONDS", "180")
    settings["CHAT_MAX_TOKENS"] = env.get("CHAT_FALLBACK_MAX_TOKENS", "384")
    settings["GENERATION_PROFILES_PATH"] = env.get(
        "GENERATION_PROFILES_PATH", str(DEFAULT_PROFILES)
    )
    settings["CHAT_REASONING_MODE"] = (
        env.get("CHAT_FALLBACK_REASONING_MODE") or "default"
    )
    settings["CHAT_INPUT_MAX_BYTES"] = (
        env.get("CHAT_FALLBACK_INPUT_MAX_BYTES") or "65536"
    )
    try:
        return load_chat_provider_settings(settings)
    except LLMProviderConfigurationError as error:
        raise LLMProviderConfigurationError(
            "CHAT_FALLBACK provider settings are invalid"
        ) from error


def _require_chat_max_tokens(value: str) -> int:
    try:
        result = int(value)
    except (ValueError, TypeError) as error:
        raise LLMProviderConfigurationError(
            "CHAT_MAX_TOKENS must be a positive integer"
        ) from error
    if result <= 0:
        raise LLMProviderConfigurationError(
            "CHAT_MAX_TOKENS must be a positive integer"
        )
    return result


def _positive_int(value):
    return _require_chat_max_tokens(value)


def _optional_float(value):
    if value is None or value == "":
        return None
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    except (ValueError, TypeError) as error:
        raise LLMProviderConfigurationError(
            "generation sampling setting must be finite"
        ) from error


def load_request_timeout(env: Mapping[str, str]) -> float:
    try:
        value = float(env.get("CHAT_REQUEST_TIMEOUT_SECONDS", "240"))
    except ValueError as error:
        raise RuntimeConfigurationError(
            "CHAT_REQUEST_TIMEOUT_SECONDS must be finite and positive"
        ) from error
    if not math.isfinite(value) or value <= 0:
        raise RuntimeConfigurationError(
            "CHAT_REQUEST_TIMEOUT_SECONDS must be finite and positive"
        )
    return value


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
        candidate_fan_out=_require_retrieval_int(
            source.get("RETRIEVAL_CANDIDATE_FAN_OUT"),
            "RETRIEVAL_CANDIDATE_FAN_OUT",
        ),
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


def load_intent_catalog_settings(
    env: Mapping[str, str] | None = None,
) -> IntentCatalogSettings:
    """Load intent catalog settings from exact environment variable names."""

    source = os.environ if env is None else env
    return IntentCatalogSettings(
        path=_require_runtime_text(
            source.get("INTENT_PROFILES_PATH"),
            "INTENT_PROFILES_PATH",
        )
    )


def build_chat_provider(settings: ChatProviderSettings) -> ChatProvider:
    """Build the configured chat provider."""

    provider = _build_provider(
        backend=settings.backend,
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout=settings.timeout_seconds,
        profile=settings.parameter_profile,
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
    timeout: float = 30.0,
    profile: ParameterProfile | None = None,
) -> object:
    if backend == "ollama":
        return OllamaProvider(
            base_url=base_url, api_key=api_key, timeout=timeout, profile=profile
        )
    if backend == "llama-cpp":
        return LlamaCppProvider(
            base_url=base_url, api_key=api_key, timeout=timeout, profile=profile
        )
    if backend == "openai-compatible":
        return OpenAICompatibleProvider(
            base_url=base_url, api_key=api_key, timeout=timeout, profile=profile
        )
    raise LLMProviderConfigurationError("unsupported provider backend")


def _require_chat_timeout(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise LLMProviderConfigurationError(
            "CHAT_TIMEOUT_SECONDS must be a finite positive number"
        ) from exc


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
