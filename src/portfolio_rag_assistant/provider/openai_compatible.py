"""Generic OpenAI-compatible HTTP provider."""

from __future__ import annotations

from numbers import Real
from typing import Any
from urllib.parse import urlparse

import httpx

from portfolio_rag_assistant.provider.contract import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingVector,
    LLMProviderConfigurationError,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMProviderTransportError,
    TokenUsage,
)


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat and embedding APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._api_key = _normalize_api_key(api_key)
        self._timeout = _require_positive_timeout(timeout)
        self._transport = transport

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "stream": False,
            "n": 1,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        response_payload = await self._post_json("/chat/completions", payload)
        return ChatResponse(
            model=_read_model(response_payload),
            message=_read_chat_message(response_payload),
            usage=_read_usage(response_payload),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "input": list(request.inputs),
            "encoding_format": "float",
        }

        response_payload = await self._post_json("/embeddings", payload)
        return EmbeddingResponse(
            model=_read_model(response_payload),
            embeddings=_read_embeddings(response_payload, len(request.inputs)),
        )

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}{path}",
                    json=payload,
                    headers=headers,
                )
        except httpx.TransportError as exc:
            raise LLMProviderTransportError("provider transport failed") from exc

        if not 200 <= response.status_code <= 299:
            raise LLMProviderRequestError(
                f"provider returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderResponseError("provider returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise LLMProviderResponseError("provider response must be a JSON object")
        return data


def _normalize_base_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMProviderConfigurationError("base_url must be set")
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LLMProviderConfigurationError(
            "base_url must be an absolute http or https API root"
        )
    return base_url


def _normalize_api_key(value: str | None) -> str | None:
    if value is None:
        return None
    api_key = value.strip()
    return api_key or None


def _require_positive_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or value <= 0:
        raise LLMProviderConfigurationError("timeout must be positive")
    return float(value)


def _read_model(payload: dict[str, Any]) -> str:
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise LLMProviderResponseError("provider response missing model")
    return model


def _read_chat_message(payload: dict[str, Any]) -> ChatMessage:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise LLMProviderResponseError("provider response must contain one choice")

    choice = choices[0]
    if not isinstance(choice, dict):
        raise LLMProviderResponseError("provider choice must be an object")

    message = choice.get("message")
    if not isinstance(message, dict):
        raise LLMProviderResponseError("provider choice missing message")

    role = message.get("role")
    content = message.get("content")
    if role != "assistant" or not isinstance(content, str) or not content.strip():
        raise LLMProviderResponseError("provider response missing assistant content")

    return ChatMessage(role="assistant", content=content)


def _read_usage(payload: dict[str, Any]) -> TokenUsage | None:
    usage = payload.get("usage")
    if usage is None:
        return None
    if not isinstance(usage, dict):
        raise LLMProviderResponseError("provider usage must be an object")

    return TokenUsage(
        input_tokens=_read_optional_non_negative_int(usage, "prompt_tokens"),
        output_tokens=_read_optional_non_negative_int(usage, "completion_tokens"),
        total_tokens=_read_optional_non_negative_int(usage, "total_tokens"),
    )


def _read_optional_non_negative_int(
    payload: dict[str, Any],
    key: str,
) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LLMProviderResponseError(f"provider usage {key} must be non-negative")
    return value


def _read_embeddings(
    payload: dict[str, Any],
    expected_count: int,
) -> tuple[EmbeddingVector, ...]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected_count:
        raise LLMProviderResponseError("provider embedding count does not match input")

    by_index: dict[int, EmbeddingVector] = {}
    for item in data:
        if not isinstance(item, dict):
            raise LLMProviderResponseError("provider embedding item must be an object")
        index = item.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise LLMProviderResponseError("provider embedding index must be an integer")
        if index in by_index:
            raise LLMProviderResponseError("provider embedding indexes must be unique")
        by_index[index] = _read_embedding_vector(item.get("embedding"))

    expected_indexes = set(range(expected_count))
    if set(by_index) != expected_indexes:
        raise LLMProviderResponseError("provider embedding indexes are incomplete")

    return tuple(by_index[index] for index in range(expected_count))


def _read_embedding_vector(value: object) -> EmbeddingVector:
    if not isinstance(value, list) or len(value) == 0:
        raise LLMProviderResponseError("provider embedding must be a non-empty list")

    vector = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, Real):
            raise LLMProviderResponseError("provider embedding values must be numbers")
        vector.append(float(item))
    return tuple(vector)
