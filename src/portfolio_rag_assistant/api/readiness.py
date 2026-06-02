"""Runtime readiness checks for deployment exposure."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


class ReadinessCheckError(RuntimeError):
    """Raised when the runtime is not ready for public traffic."""


class ReadinessCursor(Protocol):
    """Small cursor surface used by readiness checks."""

    def fetchone(self) -> tuple[Any, ...] | None: ...


class ReadinessConnection(Protocol):
    """Small connection surface used by readiness checks."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> ReadinessCursor: ...


class DatabaseReadinessService:
    """Check database, schema, and configured embedding availability."""

    def __init__(
        self,
        *,
        connection: ReadinessConnection,
        embedding_backend: str,
        embedding_model: str,
        question_collection_enabled: bool,
    ) -> None:
        self._connection = connection
        self._embedding_backend = _require_text(
            embedding_backend,
            "embedding_backend",
        )
        self._embedding_model = _require_text(embedding_model, "embedding_model")
        self._question_collection_enabled = _require_bool(
            question_collection_enabled,
            "question_collection_enabled",
        )

    async def check(self) -> None:
        """Raise when the database is not ready for public answers."""

        try:
            _require_schema(self._connection)
            if self._question_collection_enabled:
                _require_question_collection_schema(self._connection)
            _require_embedding_availability(
                self._connection,
                embedding_backend=self._embedding_backend,
                embedding_model=self._embedding_model,
            )
        except ReadinessCheckError:
            raise
        except Exception as error:
            raise ReadinessCheckError("runtime readiness check failed") from error


def _require_schema(connection: ReadinessConnection) -> None:
    row = connection.execute(
        """
        SELECT
            to_regclass('public.sources') IS NOT NULL,
            to_regclass('public.facts') IS NOT NULL,
            to_regclass('public.chunks') IS NOT NULL,
            to_regclass('public.chunk_embeddings') IS NOT NULL,
            EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'chunk_embeddings'
                  AND column_name = 'chunk_text_hash'
            )
        """
    ).fetchone()
    if row != (True, True, True, True, True):
        raise ReadinessCheckError("knowledge schema is not ready")


def _require_question_collection_schema(connection: ReadinessConnection) -> None:
    row = connection.execute(
        "SELECT to_regclass('public.question_events') IS NOT NULL"
    ).fetchone()
    if row != (True,):
        raise ReadinessCheckError("question collection schema is not ready")


def _require_embedding_availability(
    connection: ReadinessConnection,
    *,
    embedding_backend: str,
    embedding_model: str,
) -> None:
    row = connection.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM chunks
            WHERE chunks.public_visible = true
        )
        AND NOT EXISTS (
            SELECT 1
            FROM chunks
            WHERE chunks.public_visible = true
              AND NOT EXISTS (
                  SELECT 1
                  FROM chunk_embeddings
                  WHERE chunk_embeddings.chunk_id = chunks.id
                    AND chunk_embeddings.embedding_backend = %s
                    AND chunk_embeddings.embedding_model = %s
                    AND chunk_embeddings.chunk_text_hash = encode(
                        digest(convert_to(chunks.chunk_text, 'UTF8'), 'sha256'),
                        'hex'
                    )
              )
        )
        """,
        (embedding_backend, embedding_model),
    ).fetchone()
    if row != (True,):
        raise ReadinessCheckError("configured embeddings are not ready")


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReadinessCheckError(f"{field_name} must be set")
    return value.strip()


def _require_bool(value: bool, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReadinessCheckError(f"{field_name} must be a boolean")
    return value
