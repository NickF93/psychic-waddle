"""Bounded wire decoding for native and OpenAI-compatible chat streams."""

import json
from collections.abc import AsyncIterator

import httpx
from httpx_sse import SSEError, aconnect_sse

from portfolio_rag_assistant.provider.contract import (
    ChatRequest,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMProviderTransportError,
)

from .parameters import ParameterProfile, chat_payload

MAX_STREAM_BYTES = 1024 * 1024


class _LimitedStream(httpx.AsyncByteStream):
    """Bound wire bytes before a line/event decoder can buffer them."""

    def __init__(self, source):
        self.source = source

    async def __aiter__(self):
        received = 0
        async for chunk in self.source:
            received += len(chunk)
            if received > MAX_STREAM_BYTES:
                raise LLMProviderResponseError("provider stream exceeded its bound")
            yield chunk

    async def aclose(self):
        await self.source.aclose()


class _BoundedTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport):
        self.transport = (
            transport if transport is not None else httpx.AsyncHTTPTransport()
        )

    async def handle_async_request(self, request):
        response = await self.transport.handle_async_request(request)
        response.stream = _LimitedStream(response.stream)
        return response

    async def aclose(self):
        await self.transport.aclose()


def _headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _object(value: str) -> dict:
    try:
        payload = json.loads(value)
    except ValueError as error:
        raise LLMProviderResponseError(
            "provider stream contains invalid JSON"
        ) from error
    if not isinstance(payload, dict) or "error" in payload:
        raise LLMProviderResponseError("provider stream contains an error")
    return payload


async def stream_openai(
    request: ChatRequest,
    *,
    base_url: str,
    api_key: str | None,
    timeout: float,
    transport: httpx.AsyncBaseTransport | None,
    profile: ParameterProfile | None = None,
) -> AsyncIterator[str]:
    """Yield answer content only; require a successful native finish marker."""
    finished = False
    received = 0
    try:
        async with httpx.AsyncClient(
            timeout=timeout, transport=_BoundedTransport(transport)
        ) as client, aconnect_sse(
            client,
            "POST",
            f"{base_url}/chat/completions",
            headers=_headers(api_key),
            json={
                **chat_payload(
                    request,
                    stream=True,
                    profile=profile or ParameterProfile.load("openai"),
                ),
                "n": 1,
            },
        ) as stream:
            if not stream.response.is_success:
                raise LLMProviderRequestError(
                    "provider rejected the request",
                    status_code=stream.response.status_code,
                )
            async for event in stream.aiter_sse():
                received += len(event.data.encode())
                if received > MAX_STREAM_BYTES:
                    raise LLMProviderResponseError(
                        "provider stream exceeded its bound"
                    )
                if event.data == "[DONE]":
                    if not finished:
                        raise LLMProviderResponseError(
                            "provider stream ended before completion"
                        )
                    return
                payload = _object(event.data)
                choices = payload.get("choices")
                if not isinstance(choices, list) or len(choices) > 1:
                    raise LLMProviderResponseError(
                        "provider stream choices are invalid"
                    )
                for choice in choices:
                    if not isinstance(choice, dict) or not isinstance(
                        choice.get("delta", {}), dict
                    ):
                        raise LLMProviderResponseError(
                            "provider stream delta is invalid"
                        )
                    text = choice.get("delta", {}).get("content")
                    if text is not None and not isinstance(text, str):
                        raise LLMProviderResponseError(
                            "provider stream content is invalid"
                        )
                    if text:
                        if finished:
                            raise LLMProviderResponseError(
                                "provider sent content after completion"
                            )
                        yield text
                    reason = choice.get("finish_reason")
                    if reason is not None:
                        if reason != "stop":
                            raise LLMProviderResponseError(
                                "provider answer was not completed"
                            )
                        finished = True
    except (httpx.TransportError, SSEError) as error:
        raise LLMProviderTransportError("provider stream transport failed") from error
    raise LLMProviderResponseError("provider stream closed before completion")


async def stream_ollama(
    request: ChatRequest,
    *,
    base_url: str,
    api_key: str | None,
    timeout: float,
    transport: httpx.AsyncBaseTransport | None,
    profile: ParameterProfile | None = None,
) -> AsyncIterator[str]:
    """Decode native NDJSON without exposing reasoning or upstream errors."""
    received = 0
    try:
        async with httpx.AsyncClient(
            timeout=timeout, transport=_BoundedTransport(transport)
        ) as client, client.stream(
            "POST",
            f"{base_url}/chat",
            headers=_headers(api_key),
            json=chat_payload(
                request,
                stream=True,
                profile=profile or ParameterProfile.load("ollama"),
            ),
        ) as response:
            if not response.is_success:
                raise LLMProviderRequestError(
                    "provider rejected the request",
                    status_code=response.status_code,
                )
            async for line in response.aiter_lines():
                received += len(line.encode())
                if received > MAX_STREAM_BYTES:
                    raise LLMProviderResponseError(
                        "provider stream exceeded its bound"
                    )
                if not line.strip():
                    continue
                payload = _object(line)
                message = payload.get("message", {})
                if not isinstance(message, dict):
                    raise LLMProviderResponseError(
                        "provider stream message is invalid"
                    )
                text = message.get("content", "")
                if not isinstance(text, str):
                    raise LLMProviderResponseError(
                        "provider stream content is invalid"
                    )
                if text:
                    yield text
                if payload.get("done") is True:
                    if payload.get("done_reason", "stop") != "stop":
                        raise LLMProviderResponseError(
                            "provider answer was not completed"
                        )
                    return
    except httpx.TransportError as error:
        raise LLMProviderTransportError("provider stream transport failed") from error
    raise LLMProviderResponseError("provider stream closed before completion")
