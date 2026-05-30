from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from portfolio_rag_assistant.api import APICompositionError, create_runtime_api_app
from portfolio_rag_assistant.config import ProviderSettings
from portfolio_rag_assistant.provider import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


def test_runtime_api_composition_uses_configured_authorities_without_network() -> None:
    provider = FakeProvider(embeddings=((0.0, 0.0),))
    connection = FakeRetrievalConnection()
    provider_settings: list[ProviderSettings] = []
    connection_urls: list[str] = []

    app = create_runtime_api_app(
        env=_env(),
        provider_factory=lambda settings: _record_provider(
            settings,
            provider,
            provider_settings,
        ),
        connection_factory=lambda url: _record_connection(
            url,
            connection,
            connection_urls,
        ),
    )

    response = _post_chat(app)

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_answerable",
        "answer": "I do not have verified public context to answer that reliably.",
        "sources": [],
    }
    assert provider_settings == [
        ProviderSettings(
            backend="ollama",
            base_url="http://localhost:11434/api",
            chat_model="llama3.2",
            embedding_model="nomic-embed-text",
        )
    ]
    assert connection_urls == ["postgresql://portfolio:test@localhost/portfolio"]
    assert provider.embedding_requests == (
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=("Where did Niccolo work?",),
        ),
    )
    assert provider.chat_requests == ()
    assert len(connection.calls) == 2
    assert "access-control-allow-origin" not in response.headers


def test_runtime_api_composition_requires_database_url() -> None:
    env = _env()
    del env["DATABASE_URL"]

    with pytest.raises(APICompositionError, match="DATABASE_URL must be set"):
        create_runtime_api_app(
            env=env,
            provider_factory=lambda settings: FakeProvider(embeddings=((0.0,),)),
            connection_factory=lambda url: FakeRetrievalConnection(),
        )


def _post_chat(app) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/chat",
                json={"question": "Where did Niccolo work?", "language": "en"},
            )

    return asyncio.run(run())


def _record_provider(
    settings: ProviderSettings,
    provider: "FakeProvider",
    records: list[ProviderSettings],
) -> "FakeProvider":
    records.append(settings)
    return provider


def _record_connection(
    url: str,
    connection: "FakeRetrievalConnection",
    records: list[str],
) -> "FakeRetrievalConnection":
    records.append(url)
    return connection


def _env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql://portfolio:test@localhost/portfolio",
        "LLM_BACKEND": "ollama",
        "LLM_BASE_URL": "http://localhost:11434/api",
        "CHAT_MODEL": "llama3.2",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "RETRIEVAL_TOP_K": "2",
        "RETRIEVAL_MIN_SCORE": "0.25",
    }


class FakeCursor:
    def fetchall(self) -> list[tuple[Any, ...]]:
        return []


class FakeRetrievalConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> FakeCursor:
        self.calls.append((query, tuple(params)))
        return FakeCursor()


class FakeProvider:
    def __init__(self, embeddings: tuple[tuple[float, ...], ...]) -> None:
        self._embeddings = embeddings
        self.embedding_requests: tuple[EmbeddingRequest, ...] = ()
        self.chat_requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        raise AssertionError("not-answerable composition must not call chat")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.embedding_requests = (*self.embedding_requests, request)
        return EmbeddingResponse(model=request.model, embeddings=self._embeddings)
