from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest

from portfolio_rag_assistant.api import DatabaseReadinessService, ReadinessCheckError


def test_database_readiness_accepts_schema_and_configured_embeddings() -> None:
    connection = FakeReadinessConnection(schema_ready=True, embeddings_ready=True)
    service = DatabaseReadinessService(
        connection=connection,
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
    )

    asyncio.run(service.check())

    assert connection.calls[1][1] == ("ollama", "nomic-embed-text")


def test_database_readiness_rejects_missing_schema() -> None:
    service = DatabaseReadinessService(
        connection=FakeReadinessConnection(schema_ready=False, embeddings_ready=True),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
    )

    with pytest.raises(ReadinessCheckError, match="knowledge schema is not ready"):
        asyncio.run(service.check())


def test_database_readiness_rejects_missing_configured_embeddings() -> None:
    service = DatabaseReadinessService(
        connection=FakeReadinessConnection(schema_ready=True, embeddings_ready=False),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
    )

    with pytest.raises(ReadinessCheckError, match="configured embeddings"):
        asyncio.run(service.check())


def test_database_readiness_wraps_database_failures() -> None:
    service = DatabaseReadinessService(
        connection=FailingReadinessConnection(),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
    )

    with pytest.raises(ReadinessCheckError, match="runtime readiness check failed"):
        asyncio.run(service.check())


class FakeCursor:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeReadinessConnection:
    def __init__(self, *, schema_ready: bool, embeddings_ready: bool) -> None:
        self._schema_ready = schema_ready
        self._embeddings_ready = embeddings_ready
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> FakeCursor:
        self.calls.append((query, tuple(params)))
        if "to_regclass" in query:
            return FakeCursor((True, True, True, True) if self._schema_ready else None)
        if "FROM chunk_embeddings" in query:
            return FakeCursor((self._embeddings_ready,))
        raise AssertionError(f"unexpected query: {query}")


class FailingReadinessConnection:
    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> FakeCursor:
        raise RuntimeError("database unavailable")
