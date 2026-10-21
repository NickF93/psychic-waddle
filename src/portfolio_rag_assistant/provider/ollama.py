"""Ollama HTTP provider."""

from __future__ import annotations

import re
from numbers import Real
from typing import Any
from urllib.parse import urlparse

import httpx
from .parameters import ParameterProfile, chat_payload

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


class OllamaProvider:
    """Provider for Ollama native chat and embedding routes."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        profile: ParameterProfile | None = None,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._api_key = _normalize_api_key(api_key)
        self._timeout = _require_positive_timeout(timeout)
        self._transport = transport
        self._profile = profile

    async def stream_chat(self, request: ChatRequest):
        from portfolio_rag_assistant.provider.streaming import stream_ollama

        async for text in stream_ollama(
            request,
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
            transport=self._transport,
            profile=self._profile,
        ):
            yield text

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = chat_payload(
            request,
            stream=False,
            profile=self._profile or ParameterProfile.load("ollama"),
        )
        response_payload = await self._post_json("/chat", payload)
        return ChatResponse(
            model=_read_model(response_payload),
            message=_read_chat_message(response_payload),
            usage=_read_usage(response_payload),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "input": list(request.inputs),
            "truncate": False,
        }

        response_payload = await self._post_json("/embed", payload)
        return EmbeddingResponse(
            model=_read_model(response_payload),
            embeddings=_read_embeddings(response_payload, len(request.inputs)),
        )

    async def preload_model(self, *, model: str, keep_alive: str) -> None:
        payload: dict[str, Any] = {
            "model": _require_model_name(model),
            "prompt": " ",
            "stream": False,
            "keep_alive": _read_keep_alive(keep_alive),
            "options": {"num_predict": 1},
        }
        await self._post_json("/generate", payload)

    async def loaded_models(self) -> tuple[str, ...]:
        payload = await self._get_json("/ps")
        models = payload.get("models")
        if not isinstance(models, list):
            raise LLMProviderResponseError("provider model list must be a JSON array")

        loaded = []
        for model in models:
            if not isinstance(model, dict):
                raise LLMProviderResponseError("provider model entry must be an object")
            for key in ("model", "name"):
                name = model.get(key)
                if isinstance(name, str) and name.strip():
                    loaded.append(name.strip())
        return tuple(dict.fromkeys(loaded))

    async def model_is_loaded(self, *, model: str) -> bool:
        expected_model = _require_model_name(model)
        loaded_models = await self.loaded_models()
        return any(
            _model_name_matches(expected=expected_model, loaded=loaded_model)
            for loaded_model in loaded_models
        )

    async def _get_json(self, path: str) -> dict[str, Any]:
        headers = {}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    f"{self._base_url}{path}",
                    headers=headers,
                )
        except httpx.TransportError as exc:
            raise LLMProviderTransportError("provider transport failed") from exc

        return _read_json_response(response)

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

        return _read_json_response(response)


def _read_json_response(response: httpx.Response) -> dict[str, Any]:
    if not 200 <= response.status_code <= 299:
        message = f"provider returned HTTP {response.status_code}"
        raise LLMProviderRequestError(message, status_code=response.status_code)

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


def _require_model_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMProviderConfigurationError("model must be set")
    return value.strip()


def _read_keep_alive(value: str) -> str | int:
    if not isinstance(value, str) or not value.strip():
        raise LLMProviderConfigurationError("keep_alive must be set")
    keep_alive = value.strip()
    if re.fullmatch(r"-?[0-9]+", keep_alive):
        return int(keep_alive)
    return keep_alive


def _model_name_matches(*, expected: str, loaded: str) -> bool:
    if loaded == expected:
        return True
    if ":" not in expected and loaded == f"{expected}:latest":
        return True
    return False


def _read_model(payload: dict[str, Any]) -> str:
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise LLMProviderResponseError("provider response missing model")
    return model


def _read_chat_message(payload: dict[str, Any]) -> ChatMessage:
    if payload.get("done") is not True or payload.get("done_reason") != "stop":
        raise LLMProviderResponseError("provider answer was not completed")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise LLMProviderResponseError("provider response missing message")

    role = message.get("role")
    content = message.get("content")
    if role != "assistant" or not isinstance(content, str) or not content.strip():
        raise LLMProviderResponseError("provider response missing assistant content")

    return ChatMessage(role="assistant", content=content)


def _read_usage(payload: dict[str, Any]) -> TokenUsage | None:
    input_tokens = _read_optional_non_negative_int(payload, "prompt_eval_count")
    output_tokens = _read_optional_non_negative_int(payload, "eval_count")
    if input_tokens is None and output_tokens is None:
        return None

    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
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
    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != expected_count:
        raise LLMProviderResponseError("provider embedding count does not match input")

    return tuple(_read_embedding_vector(embedding) for embedding in embeddings)


def _read_embedding_vector(value: object) -> EmbeddingVector:
    if not isinstance(value, list) or len(value) == 0:
        raise LLMProviderResponseError("provider embedding must be a non-empty list")

    vector = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, Real):
            raise LLMProviderResponseError("provider embedding values must be numbers")
        vector.append(float(item))
    return tuple(vector)
