from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any

from portfolio_rag_assistant import cli
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


def test_ingest_command_validates_input_before_database_connection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [],
                "facts": [],
            }
        ),
        encoding="utf-8",
    )
    called = False

    def fail_connect_database(**kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError(kwargs)

    monkeypatch.setattr(cli, "connect_database", fail_connect_database)
    stderr = StringIO()

    exit_code = cli.run(
        ("knowledge", "ingest", str(invalid_path)),
        env=_db_env(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert called is False
    assert "sources must not be empty" in stderr.getvalue()


def test_validate_command_does_not_require_database_or_provider_config(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.run(
        ("knowledge", "validate", str(valid_path)),
        env={},
        stdout=stdout,
    )

    assert exit_code == 0
    assert "validated 1 sources, 1 facts, 1 chunks" in stdout.getvalue()


def test_ingest_command_requires_database_settings_after_valid_input(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stderr = StringIO()

    exit_code = cli.run(("knowledge", "ingest", str(valid_path)), env={}, stderr=stderr)

    assert exit_code == 2
    assert "DB_HOST must be set" in stderr.getvalue()


def test_runtime_smoke_checks_database_and_providers(monkeypatch) -> None:
    connection = FakeSmokeConnection()
    chat_provider = FakeChatProvider()
    embedding_provider = FakeEmbeddingProvider()
    stdout = StringIO()

    monkeypatch.setattr(cli, "connect_database", lambda **kwargs: connection)
    monkeypatch.setattr(cli, "build_chat_provider", lambda settings: chat_provider)
    monkeypatch.setattr(
        cli,
        "build_embedding_provider",
        lambda settings: embedding_provider,
    )

    exit_code = cli.run(
        ("runtime", "smoke"),
        env={
            **_db_env(),
            "CHAT_BACKEND": "openai-compatible",
            "CHAT_BASE_URL": "https://api.example.test/v1",
            "CHAT_MODEL": "chat-model",
            "EMBEDDING_BACKEND": "ollama",
            "EMBEDDING_BASE_URL": "http://localhost:11434/api",
            "EMBEDDING_MODEL": "nomic-embed-text",
        },
        stdout=stdout,
    )

    assert exit_code == 0
    assert "runtime smoke passed" in stdout.getvalue()
    assert connection.entered is True
    assert chat_provider.requests == (
        ChatRequest(
            model="chat-model",
            messages=(ChatMessage(role="user", content="Reply with OK."),),
            temperature=0.0,
            max_tokens=8,
        ),
    )
    assert embedding_provider.requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("runtime smoke",)),
    )


def _valid_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sources": [
            {
                "source_uri": "cv://niccolo/main",
                "title": "Niccolo Ferrari CV",
                "reviewed_at": "2026-05-28T00:00:00+00:00",
            }
        ],
        "facts": [
            {
                "source_uri": "cv://niccolo/main",
                "category": "experience",
                "fact_text": "Niccolo worked at NAIS s.r.l.",
                "source_locator": "Experience section",
                "public_visible": True,
            }
        ],
    }


def _db_env() -> dict[str, str]:
    return {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "portfolio",
        "DB_USER": "portfolio_user",
        "DB_PASSWORD": "secret",
    }


class FakeCursor:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...]:
        return self._row


class FakeSmokeConnection:
    def __init__(self) -> None:
        self.entered = False

    def __enter__(self) -> FakeSmokeConnection:
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> FakeCursor:
        if "to_regclass" in query:
            return FakeCursor((True, True, True, True))
        if "FROM chunk_embeddings" in query:
            return FakeCursor((True,))
        raise AssertionError(query)


class FakeChatProvider:
    def __init__(self) -> None:
        self.requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests = (*self.requests, request)
        return ChatResponse(
            model=request.model,
            message=ChatMessage(role="assistant", content="OK"),
        )


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests = (*self.requests, request)
        return EmbeddingResponse(model=request.model, embeddings=((1.0,),))
