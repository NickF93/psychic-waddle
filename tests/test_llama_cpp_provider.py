from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import TypeVar

import httpx
import pytest

from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    LLMProvider,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMProviderTransportError,
    LlamaCppProvider,
    OpenAICompatibleProvider,
)

T = TypeVar("T")


def run_async(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_llama_cpp_provider_satisfies_runtime_contract() -> None:
    provider = LlamaCppProvider(base_url="http://localhost:8080/v1")

    assert isinstance(provider, LLMProvider)


def test_llama_cpp_provider_does_not_subclass_generic_provider() -> None:
    assert not issubclass(LlamaCppProvider, OpenAICompatibleProvider)


def test_llama_cpp_chat_sends_payload_and_reads_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {
            "model": "local-chat",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "n": 1,
        }
        return httpx.Response(
            200,
            json={
                "model": "local-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "local answer"},
                    }
                ],
            },
        )

    provider = LlamaCppProvider(
        base_url="http://localhost:8080/v1",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.chat(
            ChatRequest(
                model="local-chat",
                messages=(ChatMessage(role="user", content="hello"),),
            )
        )
    )

    assert response.model == "local-chat"
    assert response.message == ChatMessage(role="assistant", content="local answer")
    assert response.usage is None


def test_llama_cpp_embed_sends_payload_with_optional_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer local-token"
        assert json.loads(request.content) == {
            "model": "local-embedding",
            "input": ["first", "second"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "model": "local-embedding",
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2]},
                    {"index": 1, "embedding": [0.3, 0.4]},
                ],
            },
        )

    provider = LlamaCppProvider(
        base_url="http://localhost:8080/v1",
        api_key=" local-token ",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.embed(
            EmbeddingRequest(
                model="local-embedding",
                inputs=("first", "second"),
            )
        )
    )

    assert response.model == "local-embedding"
    assert response.embeddings == ((0.1, 0.2), (0.3, 0.4))


def test_llama_cpp_provider_maps_http_errors() -> None:
    provider = LlamaCppProvider(
        base_url="http://localhost:8080/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(LLMProviderRequestError):
        run_async(
            provider.chat(
                ChatRequest(
                    model="local-chat",
                    messages=(ChatMessage(role="user", content="hello"),),
                )
            )
        )


def test_llama_cpp_provider_maps_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = LlamaCppProvider(
        base_url="http://localhost:8080/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderTransportError):
        run_async(
            provider.embed(
                EmbeddingRequest(model="local-embedding", inputs=("question",))
            )
        )


def test_llama_cpp_provider_maps_malformed_responses() -> None:
    provider = LlamaCppProvider(
        base_url="http://localhost:8080/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "model": "local-embedding",
                    "data": [{"index": 0, "embedding": []}],
                },
            )
        ),
    )

    with pytest.raises(LLMProviderResponseError):
        run_async(
            provider.embed(
                EmbeddingRequest(model="local-embedding", inputs=("question",))
            )
        )
