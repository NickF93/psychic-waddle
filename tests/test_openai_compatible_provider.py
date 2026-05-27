from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
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
    OpenAICompatibleProvider,
    TokenUsage,
)

T = TypeVar("T")


def run_async(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_openai_compatible_provider_satisfies_runtime_contract() -> None:
    provider = OpenAICompatibleProvider(base_url="https://provider.test/v1")

    assert isinstance(provider, LLMProvider)


def test_openai_compatible_chat_sends_payload_and_reads_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        assert json.loads(request.content) == {
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Where did Niccolo work?"}],
            "stream": False,
            "n": 1,
            "temperature": 0,
            "max_tokens": 128,
        }
        return httpx.Response(
            200,
            json={
                "model": "chat-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Answer."},
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                    "total_tokens": 10,
                },
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1/",
        api_key=" secret ",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.chat(
            ChatRequest(
                model="chat-model",
                messages=(ChatMessage(role="user", content="Where did Niccolo work?"),),
                temperature=0,
                max_tokens=128,
            )
        )
    )

    assert response.model == "chat-model"
    assert response.message == ChatMessage(role="assistant", content="Answer.")
    assert response.usage == TokenUsage(input_tokens=4, output_tokens=6, total_tokens=10)


def test_openai_compatible_embed_preserves_response_index_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/embeddings"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {
            "model": "embedding-model",
            "input": ["first", "second"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "model": "embedding-model",
                "data": [
                    {"index": 1, "embedding": [3, 4.5]},
                    {"index": 0, "embedding": [1, 2]},
                ],
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        transport=httpx.MockTransport(handler),
    )

    response = run_async(
        provider.embed(
            EmbeddingRequest(
                model="embedding-model",
                inputs=("first", "second"),
            )
        )
    )

    assert response.model == "embedding-model"
    assert response.embeddings == ((1.0, 2.0), (3.0, 4.5))


def test_openai_compatible_provider_maps_http_errors() -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(400)),
    )

    with pytest.raises(LLMProviderRequestError):
        run_async(
            provider.chat(
                ChatRequest(
                    model="chat-model",
                    messages=(ChatMessage(role="user", content="hello"),),
                )
            )
        )


def test_openai_compatible_provider_maps_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderTransportError):
        run_async(
            provider.embed(
                EmbeddingRequest(model="embedding-model", inputs=("question",))
            )
        )


@pytest.mark.parametrize(
    "response_factory",
    (
        lambda: httpx.Response(
            200,
            json={"model": "chat-model", "choices": []},
        ),
        lambda: httpx.Response(
            200,
            json={
                "model": "embedding-model",
                "data": [{"index": 1, "embedding": [1.0]}],
            },
        ),
    ),
)
def test_openai_compatible_provider_maps_malformed_responses(
    response_factory: Callable[[], httpx.Response],
) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        transport=httpx.MockTransport(lambda request: response_factory()),
    )

    with pytest.raises(LLMProviderResponseError):
        run_async(
            provider.chat(
                ChatRequest(
                    model="chat-model",
                    messages=(ChatMessage(role="user", content="hello"),),
                )
            )
        )
