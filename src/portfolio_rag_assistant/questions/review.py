"""Operator review store for collected unanswered questions."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

QUESTION_REVIEW_STATES: frozenset[str] = frozenset(
    ("pending", "reviewed", "ignored")
)
QUESTION_REVIEW_CATEGORIES: frozenset[str] = frozenset(
    (
        "missing_fact",
        "alias",
        "eval_case",
        "unclear",
        "off_topic",
        "private_data",
        "spam",
        "other",
    )
)


class QuestionReviewError(RuntimeError):
    """Raised when question review data cannot be managed."""


@dataclass(frozen=True, slots=True)
class QuestionEvent:
    """Collected raw question event for operator review."""

    id: int
    raw_question_text: str
    review_state: str
    review_category: str | None
    review_note: str | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not _is_positive_int(self.id):
            raise QuestionReviewError("id must be positive")
        _require_text(self.raw_question_text, "raw_question_text")
        _require_state(self.review_state)
        _require_optional_category(self.review_category)
        if self.review_note is not None:
            _require_text(self.review_note, "review_note")
        _require_text(self.created_at, "created_at")
        _require_text(self.updated_at, "updated_at")


class DatabaseCursor(Protocol):
    """Small cursor surface used by the question review store."""

    def fetchone(self) -> tuple[Any, ...] | None: ...

    def fetchall(self) -> list[tuple[Any, ...]]: ...


class DatabaseConnection(Protocol):
    """Small connection surface used by the question review store."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> DatabaseCursor: ...

    def transaction(self) -> AbstractContextManager[object]: ...


class QuestionReviewStore:
    """Persistence authority for operator-owned question review workflow."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self._connection = connection

    def list_events(
        self,
        *,
        state: str | None = None,
        limit: int = 50,
    ) -> tuple[QuestionEvent, ...]:
        """List collected question events newest first."""

        _require_optional_state(state)
        if not _is_positive_int(limit):
            raise QuestionReviewError("limit must be positive")
        where_clause = ""
        params: tuple[object, ...] = (limit,)
        if state is not None:
            where_clause = "WHERE review_state = %s"
            params = (state, limit)
        cursor = self._connection.execute(
            f"""
            SELECT
                id,
                raw_question_text,
                review_state,
                review_category,
                review_note,
                created_at,
                updated_at
            FROM question_events
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        return tuple(_event_from_row(row) for row in cursor.fetchall())

    def export_events(self, *, state: str | None = None) -> tuple[QuestionEvent, ...]:
        """Export collected question events newest first."""

        _require_optional_state(state)
        where_clause = ""
        params: tuple[object, ...] = ()
        if state is not None:
            where_clause = "WHERE review_state = %s"
            params = (state,)
        cursor = self._connection.execute(
            f"""
            SELECT
                id,
                raw_question_text,
                review_state,
                review_category,
                review_note,
                created_at,
                updated_at
            FROM question_events
            {where_clause}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        )
        return tuple(_event_from_row(row) for row in cursor.fetchall())

    def get_event(self, event_id: int) -> QuestionEvent:
        """Load one collected question event."""

        _require_event_id(event_id)
        cursor = self._connection.execute(
            """
            SELECT
                id,
                raw_question_text,
                review_state,
                review_category,
                review_note,
                created_at,
                updated_at
            FROM question_events
            WHERE id = %s
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise QuestionReviewError("question event not found")
        return _event_from_row(row)

    def mark_event(
        self,
        event_id: int,
        *,
        state: str,
        category: str | None,
        note: str | None,
    ) -> QuestionEvent:
        """Update operator-owned review fields for one event."""

        _require_event_id(event_id)
        _require_state(state)
        _require_optional_category(category)
        note = _normalize_optional_text(note)
        with self._connection.transaction():
            cursor = self._connection.execute(
                """
                UPDATE question_events
                SET review_state = %s,
                    review_category = %s,
                    review_note = %s,
                    updated_at = now()
                WHERE id = %s
                RETURNING
                    id,
                    raw_question_text,
                    review_state,
                    review_category,
                    review_note,
                    created_at,
                    updated_at
                """,
                (state, category, note, event_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise QuestionReviewError("question event not found")
        return _event_from_row(row)

    def delete_event(self, event_id: int) -> bool:
        """Delete one raw question record."""

        _require_event_id(event_id)
        with self._connection.transaction():
            cursor = self._connection.execute(
                "DELETE FROM question_events WHERE id = %s RETURNING id",
                (event_id,),
            )
            row = cursor.fetchone()
        return row is not None


def _event_from_row(row: tuple[Any, ...]) -> QuestionEvent:
    return QuestionEvent(
        id=int(row[0]),
        raw_question_text=str(row[1]),
        review_state=str(row[2]),
        review_category=_optional_text(row[3]),
        review_note=_optional_text(row[4]),
        created_at=_timestamp_text(row[5]),
        updated_at=_timestamp_text(row[6]),
    )


def _timestamp_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise QuestionReviewError("review_note must not be blank")
    return text


def _require_event_id(value: int) -> None:
    if not _is_positive_int(value):
        raise QuestionReviewError("event_id must be positive")


def _is_positive_int(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise QuestionReviewError(f"{field_name} must be a non-empty string")


def _require_optional_state(value: str | None) -> None:
    if value is not None:
        _require_state(value)


def _require_state(value: str) -> None:
    if value not in QUESTION_REVIEW_STATES:
        allowed = ", ".join(sorted(QUESTION_REVIEW_STATES))
        raise QuestionReviewError(f"review_state must be one of: {allowed}")


def _require_optional_category(value: str | None) -> None:
    if value is None:
        return
    if value not in QUESTION_REVIEW_CATEGORIES:
        allowed = ", ".join(sorted(QUESTION_REVIEW_CATEGORIES))
        raise QuestionReviewError(f"review_category must be one of: {allowed}")
