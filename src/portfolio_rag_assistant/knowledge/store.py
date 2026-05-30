"""PostgreSQL persistence for verified knowledge."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from portfolio_rag_assistant.knowledge.ingestion import (
    KnowledgeBatch,
    KnowledgeChunk,
    build_fact_chunks,
)
from portfolio_rag_assistant.knowledge.input import FactInput, SourceInput


class KnowledgeStoreError(RuntimeError):
    """Raised when verified knowledge cannot be persisted."""


@dataclass(frozen=True, slots=True)
class StoredChunk:
    """Public chunk loaded for embedding generation."""

    id: int
    chunk_text: str


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingInput:
    """Embedding vector ready for persistence."""

    chunk_id: int
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.chunk_id <= 0:
            raise KnowledgeStoreError("chunk_id must be positive")
        if not self.embedding:
            raise KnowledgeStoreError("embedding must not be empty")


class DatabaseCursor(Protocol):
    """Small cursor surface used by the knowledge store."""

    def fetchone(self) -> tuple[Any, ...] | None: ...

    def fetchall(self) -> list[tuple[Any, ...]]: ...


class DatabaseConnection(Protocol):
    """Small connection surface used by the knowledge store."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> DatabaseCursor: ...

    def transaction(self) -> AbstractContextManager[object]: ...


class KnowledgeStore:
    """Persistence authority for sources, facts, chunks, and embeddings."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self._connection = connection

    def ingest_batch(self, batch: KnowledgeBatch) -> None:
        """Persist a validated batch and reconcile only its sources."""

        chunks = build_fact_chunks(batch)
        facts_by_source = _group_facts_by_source(batch.facts)
        chunks_by_source = _group_chunks_by_source(chunks)

        with self._connection.transaction():
            source_ids = {
                source.source_uri: self._upsert_source(source)
                for source in batch.sources
            }

            for source in batch.sources:
                source_id = source_ids[source.source_uri]
                source_facts = facts_by_source.get(source.source_uri, ())
                source_chunks = chunks_by_source.get(source.source_uri, ())

                self._delete_stale_chunks(source_id, source_chunks)
                self._delete_stale_facts(source_id, source_facts)

                for fact in source_facts:
                    self._upsert_fact(source_id, fact)
                for chunk in source_chunks:
                    self._upsert_chunk(source_id, chunk)

    def list_public_chunks_missing_embedding(
        self,
        backend: str,
        model: str,
    ) -> tuple[StoredChunk, ...]:
        """Return public chunks without an embedding for backend/model."""

        cursor = self._connection.execute(
            """
            SELECT chunks.id, chunks.chunk_text
            FROM chunks
            WHERE chunks.public_visible = true
              AND NOT EXISTS (
                  SELECT 1
                  FROM chunk_embeddings
                  WHERE chunk_embeddings.chunk_id = chunks.id
                    AND chunk_embeddings.embedding_backend = %s
                    AND chunk_embeddings.embedding_model = %s
              )
            ORDER BY chunks.id
            """,
            (backend, model),
        )
        return tuple(
            StoredChunk(id=int(row[0]), chunk_text=str(row[1]))
            for row in cursor.fetchall()
        )

    def upsert_chunk_embeddings(
        self,
        *,
        backend: str,
        model: str,
        embeddings: tuple[ChunkEmbeddingInput, ...],
    ) -> None:
        """Store embeddings for one backend/model pair."""

        if not embeddings:
            return

        with self._connection.transaction():
            for embedding in embeddings:
                self._connection.execute(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id,
                        embedding_backend,
                        embedding_model,
                        embedding_dimension,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s::vector)
                    ON CONFLICT (chunk_id, embedding_backend, embedding_model)
                    DO UPDATE
                    SET embedding_dimension = EXCLUDED.embedding_dimension,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        embedding.chunk_id,
                        backend,
                        model,
                        len(embedding.embedding),
                        _format_vector(embedding.embedding),
                    ),
                )

    def _upsert_source(self, source: SourceInput) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO sources (source_uri, title, reviewed_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (source_uri) DO UPDATE
            SET title = EXCLUDED.title,
                reviewed_at = EXCLUDED.reviewed_at
            RETURNING id
            """,
            (source.source_uri, source.title, source.reviewed_at),
        )
        row = cursor.fetchone()
        if row is None:
            raise KnowledgeStoreError(f"source was not persisted: {source.source_uri}")
        return int(row[0])

    def _upsert_fact(self, source_id: int, fact: FactInput) -> None:
        self._connection.execute(
            """
            INSERT INTO facts (
                source_id,
                category,
                fact_text,
                source_locator,
                public_visible
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_id, category, fact_text) DO UPDATE
            SET source_locator = EXCLUDED.source_locator,
                public_visible = EXCLUDED.public_visible
            """,
            (
                source_id,
                fact.category,
                fact.fact_text,
                fact.source_locator,
                fact.public_visible,
            ),
        )

    def _upsert_chunk(self, source_id: int, chunk: KnowledgeChunk) -> None:
        self._connection.execute(
            """
            INSERT INTO chunks (
                source_id,
                category,
                chunk_index,
                chunk_text,
                source_locator,
                public_visible
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, chunk_index) DO UPDATE
            SET category = EXCLUDED.category,
                chunk_text = EXCLUDED.chunk_text,
                source_locator = EXCLUDED.source_locator,
                public_visible = EXCLUDED.public_visible
            """,
            (
                source_id,
                chunk.category,
                chunk.chunk_index,
                chunk.chunk_text,
                chunk.source_locator,
                chunk.public_visible,
            ),
        )

    def _delete_stale_facts(
        self,
        source_id: int,
        facts: tuple[FactInput, ...],
    ) -> None:
        if not facts:
            self._connection.execute("DELETE FROM facts WHERE source_id = %s", (source_id,))
            return

        params: list[object] = [source_id]
        clauses: list[str] = []
        for fact in facts:
            clauses.append("(category = %s AND fact_text = %s)")
            params.extend((fact.category, fact.fact_text))

        self._connection.execute(
            "DELETE FROM facts WHERE source_id = %s AND NOT ("
            + " OR ".join(clauses)
            + ")",
            params,
        )

    def _delete_stale_chunks(
        self,
        source_id: int,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> None:
        if not chunks:
            self._connection.execute("DELETE FROM chunks WHERE source_id = %s", (source_id,))
            return

        placeholders = ", ".join("%s" for _ in chunks)
        params: list[object] = [source_id]
        params.extend(chunk.chunk_index for chunk in chunks)
        self._connection.execute(
            f"""
            DELETE FROM chunks
            WHERE source_id = %s
              AND chunk_index NOT IN ({placeholders})
            """,
            params,
        )


def connect_database(
    *,
    host: str,
    port: int,
    name: str,
    user: str,
    password: str,
) -> Any:
    """Open a PostgreSQL connection for knowledge commands."""

    try:
        import psycopg
    except ImportError as error:
        raise KnowledgeStoreError("psycopg is required for database commands") from error
    return psycopg.connect(
        host=host,
        port=port,
        dbname=name,
        user=user,
        password=password,
    )


def _format_vector(embedding: tuple[float, ...]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _group_facts_by_source(
    facts: tuple[FactInput, ...],
) -> dict[str, tuple[FactInput, ...]]:
    grouped: dict[str, list[FactInput]] = {}
    for fact in facts:
        grouped.setdefault(fact.source_uri, []).append(fact)
    return {source_uri: tuple(records) for source_uri, records in grouped.items()}


def _group_chunks_by_source(
    chunks: tuple[KnowledgeChunk, ...],
) -> dict[str, tuple[KnowledgeChunk, ...]]:
    grouped: dict[str, list[KnowledgeChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.source_uri, []).append(chunk)
    return {source_uri: tuple(records) for source_uri, records in grouped.items()}
