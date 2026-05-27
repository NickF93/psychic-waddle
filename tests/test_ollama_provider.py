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
    OllamaProvider,
    TokenUsage,
)

T = TypeVar("T")


def run_async(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_ollama_provider_satisfies_runtime_contract() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434/api")

    assert isinstance(provider, LLMProvider)


def test_ollama_chat_sends_native_payload_and_reads_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 64},
        }
        return httpx.Response(
            200,
            json={
                "model": "llama3.2",
                "message": {"role": "assistant", "content": "local answer"},
                "prompt_eval_count": 7,
                "eval_count": 11,
            },
        )

    provider = OllamaProvider(
        base_url="http://localhost:11434/api/",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.chat(
            ChatRequest(
                model="llama3.2",
                messages=(ChatMessage(role="user", content="hello"),),
                temperature=0.2,
                max_tokens=64,
            )
        )
    )

    assert response.model == "llama3.2"
    assert response.message == ChatMessage(role="assistant", content="local answer")
    assert response.usage == TokenUsage(input_tokens=7, output_tokens=11, total_tokens=18)


def test_ollama_embed_uses_native_embed_endpoint_with_optional_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/embed"
        assert request.headers["authorization"] == "Bearer local-token"
        assert json.loads(request.content) == {
            "model": "nomic-embed-text",
            "input": ["first", "second"],
            "truncate": False,
        }
        return httpx.Response(
            200,
            json={
                "model": "nomic-embed-text",
                "embeddings": [[0.1, 0.2], [0.3, 0.4]],
            },
        )

    provider = OllamaProvider(
        base_url="http://localhost:11434/api",
        api_key=" local-token ",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.embed(
            EmbeddingRequest(
                model="nomic-embed-text",
                inputs=("first", "second"),
            )
        )
    )

    assert response.model == "nomic-embed-text"
    assert response.embeddings == ((0.1, 0.2), (0.3, 0.4))


def test_ollama_provider_maps_http_errors() -> None:
    provider = OllamaProvider(
        base_url="http://localhost:11434/api",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
    )

    with pytest.raises(LLMProviderRequestError):
        run_async(
            provider.chat(
                ChatRequest(
                    model="llama3.2",
                    messages=(ChatMessage(role="user", content="hello"),),
                )
            )
        )


def test_ollama_provider_maps_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = OllamaProvider(
        base_url="http://localhost:11434/api",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderTransportError):
        run_async(
            provider.embed(
                EmbeddingRequest(model="nomic-embed-text", inputs=("question",))
            )
        )


def test_ollama_provider_maps_malformed_responses() -> None:
    provider = OllamaProvider(
        base_url="http://localhost:11434/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"model": "nomic-embed-text", "embeddings": [[]]},
            )
        ),
    )

    with pytest.raises(LLMProviderResponseError):
        run_async(
            provider.embed(
                EmbeddingRequest(model="nomic-embed-text", inputs=("question",))
            )
        )
