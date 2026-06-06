from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx
import pytest

from portfolio_rag_assistant.api import APICompositionError, create_runtime_api_app
from portfolio_rag_assistant.config import (
    ChatProviderSettings,
    DatabaseSettings,
    EmbeddingProviderSettings,
    RuntimeConfigurationError,
)
from portfolio_rag_assistant.intent import QuestionIntentProfileError
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_api_composition_uses_separate_chat_and_embedding_authorities() -> None:
    chat_provider = FakeChatProvider("unused")
    embedding_provider = FakeEmbeddingProvider(embeddings=((0.0, 0.0),))
    connection = FakeRetrievalConnection()
    chat_settings: list[ChatProviderSettings] = []
    embedding_settings: list[EmbeddingProviderSettings] = []
    database_settings: list[DatabaseSettings] = []

    app = create_runtime_api_app(
        env=_env(),
        chat_provider_factory=lambda settings: _record_chat_provider(
            settings,
            chat_provider,
            chat_settings,
        ),
        embedding_provider_factory=lambda settings: _record_embedding_provider(
            settings,
            embedding_provider,
            embedding_settings,
        ),
        connection_factory=lambda settings: _record_connection(
            settings,
            connection,
            database_settings,
        ),
    )

    response = _post_chat(app)

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_answerable",
        "answer": "I do not have verified public context to answer that reliably.",
        "sources": [],
        "notices": [],
    }
    assert chat_settings == [
        ChatProviderSettings(
            backend="openai-compatible",
            base_url="https://api.example.test/v1",
            model="chat-model",
            api_key="chat-secret",
        )
    ]
    assert embedding_settings == [
        EmbeddingProviderSettings(
            backend="ollama",
            base_url="http://localhost:11434/api",
            model="nomic-embed-text",
            api_key=None,
        )
    ]
    assert database_settings == [
        DatabaseSettings(
            host="db",
            port=5432,
            name="portfolio",
            user="portfolio_user",
            password="p@ss/word:%",
        )
    ]
    anchor_questions = _semantic_anchor_questions()
    assert embedding_provider.embedding_requests == (
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=("Where did Niccolo work?",),
        ),
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=anchor_questions,
        ),
    )
    assert chat_provider.chat_requests == ()
    assert len(connection.calls) == 3
    intent_calls = [
        (query, params)
        for query, params in connection.calls
        if "WITH intent_query" in query
    ]
    assert len(intent_calls) == 1
    assert "work history" in str(intent_calls[0][1][0])
    assert intent_calls[0][1][1] == ["experience"]
    assert not any("INSERT INTO question_events" in query for query, _ in connection.calls)
    assert "access-control-allow-origin" not in response.headers


def test_runtime_api_composition_collects_unanswered_questions_when_enabled() -> None:
    connection = FakeRetrievalConnection()
    env = _env()
    env["QUESTION_COLLECTION_ENABLED"] = "true"

    app = create_runtime_api_app(
        env=env,
        chat_provider_factory=lambda settings: FakeChatProvider("unused"),
        embedding_provider_factory=lambda settings: FakeEmbeddingProvider(
            embeddings=((0.0, 0.0),)
        ),
        connection_factory=lambda settings: connection,
    )

    response = _post_chat(app)

    assert response.status_code == 200
    assert response.json()["notices"] == [{"code": "question_recorded"}]
    assert any(
        "INSERT INTO question_events (raw_question_text)" in query
        and params == ("Where did Niccolo work?",)
        for query, params in connection.calls
    )


def test_runtime_api_composition_uses_configured_intent_catalog(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = json.loads(
        (ROOT / "config" / "intent-profiles.json").read_text(encoding="utf-8")
    )
    for profile in payload["profiles"]:
        if profile["intent"] == "workplace":
            profile["trigger_groups"] = [["unmatched-workplace-trigger"]]
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    connection = FakeRetrievalConnection()
    env = _env()
    env["INTENT_PROFILES_PATH"] = str(catalog_path)

    app = create_runtime_api_app(
        env=env,
        chat_provider_factory=lambda settings: FakeChatProvider("unused"),
        embedding_provider_factory=lambda settings: FakeEmbeddingProvider(
            embeddings=((0.0, 0.0),)
        ),
        connection_factory=lambda settings: connection,
    )

    response = _post_chat(app)

    assert response.status_code == 200
    assert not any("WITH intent_query" in query for query, _params in connection.calls)


def test_runtime_api_composition_requires_database_settings() -> None:
    env = _env()
    del env["DB_HOST"]

    with pytest.raises(RuntimeConfigurationError, match="DB_HOST must be set"):
        create_runtime_api_app(
            env=env,
            chat_provider_factory=lambda settings: FakeChatProvider("unused"),
            embedding_provider_factory=lambda settings: FakeEmbeddingProvider(
                embeddings=((0.0,),)
            ),
            connection_factory=lambda settings: FakeRetrievalConnection(),
        )


def test_runtime_api_composition_requires_intent_catalog_settings() -> None:
    env = _env()
    del env["INTENT_PROFILES_PATH"]

    with pytest.raises(
        RuntimeConfigurationError,
        match="INTENT_PROFILES_PATH must be set",
    ):
        create_runtime_api_app(
            env=env,
            chat_provider_factory=lambda settings: FakeChatProvider("unused"),
            embedding_provider_factory=lambda settings: FakeEmbeddingProvider(
                embeddings=((0.0,),)
            ),
            connection_factory=lambda settings: FakeRetrievalConnection(),
        )


def test_runtime_api_composition_rejects_stale_semantic_calibration() -> None:
    env = _env()
    env["EMBEDDING_MODEL"] = "different-embedding-model"
    provider_calls: list[str] = []
    connection_calls: list[str] = []

    with pytest.raises(
        APICompositionError,
        match="intent semantic calibration must match",
    ):
        create_runtime_api_app(
            env=env,
            chat_provider_factory=lambda settings: _record_unexpected_chat_provider(
                "chat",
                provider_calls,
            ),
            embedding_provider_factory=lambda settings: (
                _record_unexpected_embedding_provider(
                    "embedding",
                    provider_calls,
                )
            ),
            connection_factory=lambda settings: _record_unexpected_connection(
                connection_calls
            ),
        )

    assert provider_calls == []
    assert connection_calls == []


@pytest.mark.parametrize(
    ("catalog_path", "catalog_text", "error"),
    (
        (
            "missing-intent-profiles.json",
            None,
            "intent catalog file not found",
        ),
        (
            "invalid-intent-profiles.json",
            "{",
            "intent catalog must be valid JSON",
        ),
    ),
)
def test_runtime_api_composition_rejects_invalid_intent_catalog_path(
    tmp_path: Path,
    catalog_path: str,
    catalog_text: str | None,
    error: str,
) -> None:
    path = tmp_path / catalog_path
    if catalog_text is not None:
        path.write_text(catalog_text, encoding="utf-8")
    env = _env()
    env["INTENT_PROFILES_PATH"] = str(path)
    provider_calls: list[str] = []
    connection_calls: list[str] = []

    with pytest.raises(QuestionIntentProfileError, match=error):
        create_runtime_api_app(
            env=env,
            chat_provider_factory=lambda settings: _record_unexpected_chat_provider(
                "chat",
                provider_calls,
            ),
            embedding_provider_factory=lambda settings: (
                _record_unexpected_embedding_provider(
                    "embedding",
                    provider_calls,
                )
            ),
            connection_factory=lambda settings: _record_unexpected_connection(
                connection_calls
            ),
        )

    assert provider_calls == []
    assert connection_calls == []


def test_runtime_api_composition_wraps_database_connection_failure() -> None:
    def fail_connection(settings: DatabaseSettings) -> object:
        raise APICompositionError("database connection failed")

    with pytest.raises(APICompositionError, match="database connection failed"):
        create_runtime_api_app(
            env=_env(),
            chat_provider_factory=lambda settings: FakeChatProvider("unused"),
            embedding_provider_factory=lambda settings: FakeEmbeddingProvider(
                embeddings=((0.0,),)
            ),
            connection_factory=fail_connection,
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


def _record_chat_provider(
    settings: ChatProviderSettings,
    provider: "FakeChatProvider",
    records: list[ChatProviderSettings],
) -> "FakeChatProvider":
    records.append(settings)
    return provider


def _record_embedding_provider(
    settings: EmbeddingProviderSettings,
    provider: "FakeEmbeddingProvider",
    records: list[EmbeddingProviderSettings],
) -> "FakeEmbeddingProvider":
    records.append(settings)
    return provider


def _record_connection(
    settings: DatabaseSettings,
    connection: "FakeRetrievalConnection",
    records: list[DatabaseSettings],
) -> "FakeRetrievalConnection":
    records.append(settings)
    return connection


def _record_unexpected_chat_provider(
    name: str,
    records: list[str],
) -> FakeChatProvider:
    records.append(name)
    return FakeChatProvider("unused")


def _record_unexpected_embedding_provider(
    name: str,
    records: list[str],
) -> FakeEmbeddingProvider:
    records.append(name)
    return FakeEmbeddingProvider(embeddings=((0.0,),))


def _record_unexpected_connection(records: list[str]) -> FakeRetrievalConnection:
    records.append("connection")
    return FakeRetrievalConnection()


def _env() -> dict[str, str]:
    return {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "portfolio",
        "DB_USER": "portfolio_user",
        "DB_PASSWORD": "p@ss/word:%",
        "CHAT_BACKEND": "openai-compatible",
        "CHAT_BASE_URL": "https://api.example.test/v1",
        "CHAT_API_KEY": "chat-secret",
        "CHAT_MODEL": "chat-model",
        "EMBEDDING_BACKEND": "ollama",
        "EMBEDDING_BASE_URL": "http://localhost:11434/api",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "RETRIEVAL_TOP_K": "2",
        "RETRIEVAL_CANDIDATE_FAN_OUT": "6",
        "RETRIEVAL_MIN_SCORE": "0.25",
        "INTENT_PROFILES_PATH": str(ROOT / "config" / "intent-profiles.json"),
        "QUESTION_COLLECTION_ENABLED": "false",
    }


class FakeCursor:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self._row = row

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeTransaction(AbstractContextManager[object]):
    def __enter__(self) -> object:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeRetrievalConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> FakeCursor:
        self.calls.append((query, tuple(params)))
        if "INSERT INTO question_events" in query:
            return FakeCursor((101,))
        return FakeCursor()

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


class FakeChatProvider:
    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text
        self.chat_requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        return ChatResponse(
            model=request.model,
            message=ChatMessage(role="assistant", content=self.answer_text),
        )


class FakeEmbeddingProvider:
    def __init__(self, embeddings: tuple[tuple[float, ...], ...]) -> None:
        self._embeddings = embeddings
        self.embedding_requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.embedding_requests = (*self.embedding_requests, request)
        if len(self.embedding_requests) == 1:
            embeddings = self._embeddings
        else:
            embeddings = tuple(
                tuple(-value for value in self._embeddings[0])
                for _input in request.inputs
            )
        return EmbeddingResponse(model=request.model, embeddings=embeddings)


def _semantic_anchor_questions() -> tuple[str, ...]:
    payload = json.loads(
        (ROOT / "config" / "intent-profiles.json").read_text(encoding="utf-8")
    )
    return tuple(
        question
        for profile in payload["profiles"]
        for question in profile["semantic_example_questions"]
    )
