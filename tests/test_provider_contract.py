from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import pytest

from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMProviderTransportError,
    TokenUsage,
)

T = TypeVar("T")


class FakeProvider:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            model=request.model,
            message=ChatMessage(
                role="assistant",
                content=f"Received {len(request.messages)} message(s).",
            ),
            usage=TokenUsage(input_tokens=3, output_tokens=5, total_tokens=8),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        embeddings = tuple(
            (float(index), float(len(input_text)))
            for index, input_text in enumerate(request.inputs)
        )
        return EmbeddingResponse(model=request.model, embeddings=embeddings)


def run_async(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_fake_provider_satisfies_runtime_contract() -> None:
    provider = FakeProvider()

    assert isinstance(provider, LLMProvider)


def test_fake_provider_chat_returns_provider_neutral_response() -> None:
    provider = FakeProvider()
    request = ChatRequest(
        model="chat-model",
        messages=(ChatMessage(role="user", content="Where did Niccolo work?"),),
        temperature=0,
        max_tokens=128,
    )

    response = run_async(provider.chat(request))

    assert response.model == "chat-model"
    assert response.message == ChatMessage(
        role="assistant",
        content="Received 1 message(s).",
    )
    assert response.usage == TokenUsage(input_tokens=3, output_tokens=5, total_tokens=8)


def test_fake_provider_embed_preserves_input_order_and_count() -> None:
    provider = FakeProvider()
    request = EmbeddingRequest(
        model="embedding-model",
        inputs=("short", "longer text"),
    )

    response = run_async(provider.embed(request))

    assert response.model == "embedding-model"
    assert len(response.embeddings) == len(request.inputs)
    assert response.embeddings == ((0.0, 5.0), (1.0, 11.0))


@pytest.mark.parametrize(
    "error_type",
    (
        LLMProviderConfigurationError,
        LLMProviderRequestError,
        LLMProviderTransportError,
        LLMProviderResponseError,
    ),
)
def test_provider_specific_errors_share_common_base(
    error_type: type[LLMProviderError],
) -> None:
    with pytest.raises(LLMProviderError):
        raise error_type("provider failure")


@pytest.mark.parametrize(
    "factory",
    (
        lambda: ChatRequest(model="", messages=(ChatMessage(role="user", content="x"),)),
        lambda: ChatRequest(model="chat-model", messages=()),
        lambda: ChatRequest(
            model="chat-model",
            messages=(ChatMessage(role="user", content="x"),),
            temperature=3,
        ),
        lambda: EmbeddingRequest(model="embedding-model", inputs=()),
        lambda: EmbeddingRequest(model="embedding-model", inputs=("",)),
    ),
)
def test_request_models_reject_invalid_values(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize(
    "response",
    (
        lambda: ChatResponse(
            model="chat-model",
            message=ChatMessage(role="user", content="not a provider answer"),
        ),
        lambda: EmbeddingResponse(model="embedding-model", embeddings=()),
        lambda: EmbeddingResponse(model="embedding-model", embeddings=((1,),)),
    ),
)
def test_response_models_reject_invalid_values(response: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        response()
