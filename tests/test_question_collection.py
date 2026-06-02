from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

import pytest

from portfolio_rag_assistant.questions import (
    DisabledQuestionCollector,
    PostgreSQLQuestionCollector,
    QuestionCollectionRequest,
    QuestionCollectionRequestError,
    QuestionCollectionResult,
    QuestionCollectionStoreError,
)


def test_question_collection_request_strips_raw_text() -> None:
    request = QuestionCollectionRequest(" What is missing? ")

    assert request.raw_question_text == "What is missing?"


@pytest.mark.parametrize("raw_question_text", ("", "   "))
def test_question_collection_request_rejects_blank_text(
    raw_question_text: str,
) -> None:
    with pytest.raises(QuestionCollectionRequestError):
        QuestionCollectionRequest(raw_question_text)


def test_question_collection_result_requires_valid_event_id() -> None:
    QuestionCollectionResult(recorded=True, event_id=1)
    QuestionCollectionResult(recorded=False)

    with pytest.raises(QuestionCollectionRequestError):
        QuestionCollectionResult(recorded=True)
    with pytest.raises(QuestionCollectionRequestError):
        QuestionCollectionResult(recorded=False, event_id=1)


def test_disabled_question_collector_writes_nothing() -> None:
    result = _run(
        DisabledQuestionCollector().collect(
            QuestionCollectionRequest("Why was this unanswered?")
        )
    )

    assert result == QuestionCollectionResult(recorded=False)


def test_postgres_question_collector_persists_raw_question_only() -> None:
    connection = FakeConnection(row=(42,))
    collector = PostgreSQLQuestionCollector(connection)

    result = _run(
        collector.collect(
            QuestionCollectionRequest("Did Niccolo work somewhere else?")
        )
    )

    assert result == QuestionCollectionResult(recorded=True, event_id=42)
    assert connection.transaction_count == 1
    assert len(connection.calls) == 1
    query, params = connection.calls[0]
    assert "INSERT INTO question_events (raw_question_text)" in query
    assert "RETURNING id" in query
    assert params == ("Did Niccolo work somewhere else?",)
    normalized_query = " ".join(query.lower().split())
    for forbidden in (
        "ip",
        "user_agent",
        "cookie",
        "session",
        "language",
        "answer",
        "source",
        "score",
        "metadata",
    ):
        assert forbidden not in normalized_query


def test_postgres_question_collector_sanitizes_database_failures() -> None:
    collector = PostgreSQLQuestionCollector(
        FailingConnection(RuntimeError("database password leaked"))
    )

    with pytest.raises(QuestionCollectionStoreError) as error:
        _run(
            collector.collect(
                QuestionCollectionRequest("Why was this not answerable?")
            )
        )

    assert str(error.value) == "question collection failed"
    assert "database password" not in str(error.value)


def test_postgres_question_collector_rejects_missing_returning_row() -> None:
    collector = PostgreSQLQuestionCollector(FakeConnection(row=None))

    with pytest.raises(QuestionCollectionStoreError, match="question collection failed"):
        _run(
            collector.collect(
                QuestionCollectionRequest("Why was this not answerable?")
            )
        )


def _run(awaitable):
    return asyncio.run(awaitable)


class FakeCursor:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeTransaction(AbstractContextManager[object]):
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> object:
        self._connection.transaction_count += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeConnection:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.transaction_count = 0

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> FakeCursor:
        self.calls.append((query, params))
        return FakeCursor(self._row)


class FailingConnection(FakeConnection):
    def __init__(self, error: Exception) -> None:
        super().__init__(row=None)
        self._error = error

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> FakeCursor:
        raise self._error
