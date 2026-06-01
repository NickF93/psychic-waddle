from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

import pytest

from portfolio_rag_assistant.questions import (
    QuestionEvent,
    QuestionReviewError,
    QuestionReviewStore,
)


def test_question_review_store_lists_events_with_state_and_limit() -> None:
    connection = FakeConnection(
        rows=[
            _row(
                event_id=7,
                question="Where else did Niccolo work?",
                state="pending",
            )
        ],
    )

    events = QuestionReviewStore(connection).list_events(state="pending", limit=10)

    assert events == (
        QuestionEvent(
            id=7,
            raw_question_text="Where else did Niccolo work?",
            review_state="pending",
            review_category=None,
            review_note=None,
            created_at="2026-06-01T12:00:00+00:00",
            updated_at="2026-06-01T12:00:00+00:00",
        ),
    )
    query, params = connection.calls[0]
    assert "FROM question_events" in query
    assert "WHERE review_state = %s" in query
    assert "%s IS NULL" not in query
    assert "ORDER BY created_at DESC, id DESC" in query
    assert params == ("pending", 10)


def test_question_review_store_lists_events_without_state_filter() -> None:
    connection = FakeConnection(rows=[_row(event_id=3, question="Missing fact?")])

    events = QuestionReviewStore(connection).list_events(limit=25)

    assert tuple(event.id for event in events) == (3,)
    query, params = connection.calls[0]
    assert "WHERE review_state = %s" not in query
    assert "%s IS NULL" not in query
    assert params == (25,)


def test_question_review_store_exports_events_without_limit() -> None:
    connection = FakeConnection(rows=[_row(event_id=3, question="Missing fact?")])

    events = QuestionReviewStore(connection).export_events()

    assert tuple(event.id for event in events) == (3,)
    query, params = connection.calls[0]
    assert "LIMIT" not in query
    assert "WHERE review_state = %s" not in query
    assert "%s IS NULL" not in query
    assert params == ()


def test_question_review_store_exports_events_with_state_filter() -> None:
    connection = FakeConnection(rows=[_row(event_id=8, question="Ignored?")])

    events = QuestionReviewStore(connection).export_events(state="ignored")

    assert tuple(event.id for event in events) == (8,)
    query, params = connection.calls[0]
    assert "WHERE review_state = %s" in query
    assert "%s IS NULL" not in query
    assert params == ("ignored",)


def test_question_review_store_loads_one_event() -> None:
    connection = FakeConnection(rows=[_row(event_id=5, question="One event?")])

    event = QuestionReviewStore(connection).get_event(5)

    assert event.id == 5
    assert event.raw_question_text == "One event?"
    assert connection.calls[0][1] == (5,)


def test_question_review_store_marks_operator_owned_fields() -> None:
    connection = FakeConnection(
        rows=[
            _row(
                event_id=9,
                question="Can this be an alias?",
                state="reviewed",
                category="alias",
                note="Use as alias candidate.",
            )
        ],
    )

    event = QuestionReviewStore(connection).mark_event(
        9,
        state="reviewed",
        category="alias",
        note="  Use as alias candidate.  ",
    )

    assert event.review_state == "reviewed"
    assert event.review_category == "alias"
    assert event.review_note == "Use as alias candidate."
    assert connection.transaction_count == 1
    query, params = connection.calls[0]
    assert "UPDATE question_events" in query
    assert params == ("reviewed", "alias", "Use as alias candidate.", 9)


def test_question_review_store_deletes_raw_question_record() -> None:
    connection = FakeConnection(rows=[(4,)])

    deleted = QuestionReviewStore(connection).delete_event(4)

    assert deleted is True
    assert connection.transaction_count == 1
    assert connection.calls[0][1] == (4,)


def test_question_review_store_reports_missing_event() -> None:
    connection = FakeConnection(rows=[])

    with pytest.raises(QuestionReviewError, match="question event not found"):
        QuestionReviewStore(connection).get_event(404)


@pytest.mark.parametrize("limit", (0, -1))
def test_question_review_store_rejects_invalid_limits(limit: int) -> None:
    with pytest.raises(QuestionReviewError, match="limit must be positive"):
        QuestionReviewStore(FakeConnection(rows=[])).list_events(limit=limit)


def test_question_review_store_rejects_invalid_review_values() -> None:
    store = QuestionReviewStore(FakeConnection(rows=[]))

    with pytest.raises(QuestionReviewError, match="review_state must be one of"):
        store.list_events(state="new")
    with pytest.raises(QuestionReviewError, match="review_category must be one of"):
        store.mark_event(1, state="reviewed", category="secret", note=None)
    with pytest.raises(QuestionReviewError, match="review_note must not be blank"):
        store.mark_event(1, state="reviewed", category=None, note=" ")


def _row(
    *,
    event_id: int,
    question: str,
    state: str = "pending",
    category: str | None = None,
    note: str | None = None,
) -> tuple[Any, ...]:
    timestamp = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    return (event_id, question, state, category, note, timestamp, timestamp)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


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
    def __init__(self, *, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.transaction_count = 0

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> FakeCursor:
        self.calls.append((query, params))
        return FakeCursor(self._rows)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)
