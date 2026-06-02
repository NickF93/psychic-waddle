"""Provider-neutral contracts for model I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ChatRole = Literal["system", "user", "assistant"]
EmbeddingVector = tuple[float, ...]

ALLOWED_CHAT_ROLES: frozenset[str] = frozenset(("system", "user", "assistant"))


class LLMProviderError(Exception):
    """Base error for provider-owned failures."""


class LLMProviderConfigurationError(LLMProviderError):
    """Raised when a provider is configured incorrectly."""


class LLMProviderRequestError(LLMProviderError):
    """Raised when the provider rejects a valid contract request."""


class LLMProviderTransportError(LLMProviderError):
    """Raised when provider transport fails."""


class LLMProviderResponseError(LLMProviderError):
    """Raised when a provider response cannot satisfy the contract."""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Optional token accounting returned by a provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        _require_optional_non_negative_int(self.input_tokens, "input_tokens")
        _require_optional_non_negative_int(self.output_tokens, "output_tokens")
        _require_optional_non_negative_int(self.total_tokens, "total_tokens")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Provider-neutral chat message."""

    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in ALLOWED_CHAT_ROLES:
            allowed = ", ".join(sorted(ALLOWED_CHAT_ROLES))
            raise ValueError(f"role must be one of: {allowed}")
        _require_non_empty_text(self.content, "content")


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Provider-neutral chat completion request."""

    model: str
    messages: tuple[ChatMessage, ...]
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")
        _require_non_empty_sequence(self.messages, "messages")
        _require_items_of_type(self.messages, ChatMessage, "messages")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        _require_optional_positive_int(self.max_tokens, "max_tokens")


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Provider-neutral chat completion response."""

    model: str
    message: ChatMessage
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")
        if not isinstance(self.message, ChatMessage):
            raise ValueError("message must be a ChatMessage")
        if self.message.role != "assistant":
            raise ValueError("message role must be assistant")
        if self.usage is not None and not isinstance(self.usage, TokenUsage):
            raise ValueError("usage must be a TokenUsage")


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Provider-neutral embedding request."""

    model: str
    inputs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")
        _require_non_empty_sequence(self.inputs, "inputs")
        for index, item in enumerate(self.inputs):
            _require_non_empty_text(item, f"inputs[{index}]")


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    """Provider-neutral embedding response."""

    model: str
    embeddings: tuple[EmbeddingVector, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")
        _require_non_empty_sequence(self.embeddings, "embeddings")
        for index, vector in enumerate(self.embeddings):
            _require_non_empty_sequence(vector, f"embeddings[{index}]")
            for value in vector:
                if not isinstance(value, float):
                    raise ValueError("embedding values must be floats")


@runtime_checkable
class ChatProvider(Protocol):
    """Provider-owned chat model I/O."""

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Return one chat response for a provider-neutral request."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Provider-owned embedding model I/O."""

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Return embeddings in the same order as request inputs."""


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_non_empty_sequence(value: tuple[object, ...], field_name: str) -> None:
    if not isinstance(value, tuple) or len(value) == 0:
        raise ValueError(f"{field_name} must be a non-empty tuple")


def _require_items_of_type(
    values: tuple[object, ...], item_type: type[object], field_name: str
) -> None:
    if not all(isinstance(value, item_type) for value in values):
        raise ValueError(f"{field_name} must contain only {item_type.__name__}")


def _require_optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or value <= 0):
        raise ValueError(f"{field_name} must be a positive integer")


def _require_optional_non_negative_int(value: int | None, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer")
