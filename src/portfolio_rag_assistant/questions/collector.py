"""PostgreSQL-backed unanswered-question collection."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol

from portfolio_rag_assistant.questions.contract import (
    QuestionCollectionRequest,
    QuestionCollectionResult,
    QuestionCollectionStoreError,
)


class DatabaseCursor(Protocol):
    """Small cursor surface used by the question collector."""

    def fetchone(self) -> tuple[Any, ...] | None: ...


class DatabaseConnection(Protocol):
    """Small connection surface used by the question collector."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> DatabaseCursor: ...

    def transaction(self) -> AbstractContextManager[object]: ...


class DisabledQuestionCollector:
    """Question collector used when collection is explicitly disabled."""

    async def collect(
        self,
        request: QuestionCollectionRequest,
    ) -> QuestionCollectionResult:
        """Intentionally ignore the valid question collection request."""

        return QuestionCollectionResult(recorded=False)


class PostgreSQLQuestionCollector:
    """Persist raw unanswered-question text for operator review."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self._connection = connection

    async def collect(
        self,
        request: QuestionCollectionRequest,
    ) -> QuestionCollectionResult:
        """Persist one raw unanswered question with no runtime metadata."""

        try:
            with self._connection.transaction():
                cursor = self._connection.execute(
                    """
                    INSERT INTO question_events (raw_question_text)
                    VALUES (%s)
                    RETURNING id
                    """,
                    (request.raw_question_text,),
                )
                row = cursor.fetchone()
        except Exception as error:
            raise QuestionCollectionStoreError("question collection failed") from error

        if row is None:
            raise QuestionCollectionStoreError("question collection failed")
        return QuestionCollectionResult(recorded=True, event_id=int(row[0]))
