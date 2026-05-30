"""PostgreSQL retrieval over verified public knowledge."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from portfolio_rag_assistant.knowledge import KnowledgeCategory
from portfolio_rag_assistant.provider import EmbeddingRequest, LLMProvider
from portfolio_rag_assistant.retrieval.contract import (
    RetrievedContext,
    RetrievalConfigurationError,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalScore,
    RetrievalStoreError,
)


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    """Internal ranked chunk candidate loaded from PostgreSQL."""

    chunk_id: int
    chunk_text: str
    category: KnowledgeCategory
    source_uri: str
    source_title: str
    source_locator: str | None
    vector_score: float | None = None
    keyword_score: float | None = None

    @property
    def combined_score(self) -> float:
        scores = (
            score
            for score in (self.vector_score, self.keyword_score)
            if score is not None
        )
        return max(scores, default=0.0)

    def to_context(self) -> RetrievedContext:
        """Convert the internal candidate into the public retrieval contract."""

        return RetrievedContext(
            chunk_id=self.chunk_id,
            chunk_text=self.chunk_text,
            category=self.category,
            source_uri=self.source_uri,
            source_title=self.source_title,
            source_locator=self.source_locator,
            score=RetrievalScore(
                combined_score=self.combined_score,
                vector_score=self.vector_score,
                keyword_score=self.keyword_score,
            ),
        )


class RetrievalDatabaseCursor(Protocol):
    """Small cursor surface used by PostgreSQL retrieval."""

    def fetchall(self) -> list[tuple[Any, ...]]: ...


class RetrievalDatabaseConnection(Protocol):
    """Small read-only connection surface used by PostgreSQL retrieval."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> RetrievalDatabaseCursor: ...


class PostgreSQLRetriever:
    """Retriever implementation for PostgreSQL and pgvector."""

    def __init__(
        self,
        *,
        connection: RetrievalDatabaseConnection,
        provider: LLMProvider,
        embedding_backend: str,
        embedding_model: str,
        min_score: float,
    ) -> None:
        self._connection = connection
        self._provider = provider
        self._embedding_backend = _require_text(embedding_backend, "embedding_backend")
        self._embedding_model = _require_text(embedding_model, "embedding_model")
        self._min_score = _require_score(min_score, "min_score")

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """Return ranked public source-backed context for a question."""

        embedding_response = await self._provider.embed(
            EmbeddingRequest(model=self._embedding_model, inputs=(request.question,))
        )
        if len(embedding_response.embeddings) != 1:
            raise RetrievalStoreError("provider returned the wrong embedding count")

        vector_candidates = self._search_vectors(
            query_embedding=embedding_response.embeddings[0],
            limit=request.top_k,
        )
        keyword_candidates = self._search_keywords(
            question=request.question,
            limit=request.top_k,
        )
        results = tuple(
            candidate.to_context()
            for candidate in _rank_candidates(
                _merge_candidates(vector_candidates, keyword_candidates),
                top_k=request.top_k,
                min_score=self._min_score,
            )
        )
        return RetrievalResponse(question=request.question, results=results)

    def _search_vectors(
        self,
        *,
        query_embedding: tuple[float, ...],
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        cursor = self._connection.execute(
            """
            SELECT
                chunks.id,
                chunks.chunk_text,
                chunks.category,
                sources.source_uri,
                sources.title,
                chunks.source_locator,
                GREATEST(0.0, 1.0 - (chunk_embeddings.embedding <=> %s::vector))
                    AS vector_score
            FROM chunk_embeddings
            JOIN chunks ON chunks.id = chunk_embeddings.chunk_id
            JOIN sources ON sources.id = chunks.source_id
            WHERE chunks.public_visible = true
              AND chunk_embeddings.embedding_backend = %s
              AND chunk_embeddings.embedding_model = %s
            ORDER BY vector_score DESC, chunks.id ASC
            LIMIT %s
            """,
            (
                _format_vector(query_embedding),
                self._embedding_backend,
                self._embedding_model,
                limit,
            ),
        )
        return tuple(_vector_candidate_from_row(row) for row in cursor.fetchall())

    def _search_keywords(
        self,
        *,
        question: str,
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        cursor = self._connection.execute(
            """
            WITH keyword_query AS (
                SELECT plainto_tsquery('simple', %s) AS value
            )
            SELECT
                chunks.id,
                chunks.chunk_text,
                chunks.category,
                sources.source_uri,
                sources.title,
                chunks.source_locator,
                LEAST(
                    1.0,
                    ts_rank_cd(
                        to_tsvector('simple', chunks.chunk_text),
                        keyword_query.value
                    )::double precision
                ) AS keyword_score
            FROM chunks
            JOIN sources ON sources.id = chunks.source_id
            CROSS JOIN keyword_query
            WHERE chunks.public_visible = true
              AND to_tsvector('simple', chunks.chunk_text) @@ keyword_query.value
            ORDER BY keyword_score DESC, chunks.id ASC
            LIMIT %s
            """,
            (question, limit),
        )
        return tuple(_keyword_candidate_from_row(row) for row in cursor.fetchall())


def _rank_candidates(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    top_k: int,
    min_score: float,
) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        candidate
        for candidate in sorted(
            candidates,
            key=lambda item: (
                -item.combined_score,
                -(item.vector_score or 0.0),
                -(item.keyword_score or 0.0),
                item.chunk_id,
            ),
        )
        if candidate.combined_score >= min_score
    )[:top_k]


def _merge_candidates(
    *candidate_groups: tuple[RetrievalCandidate, ...],
) -> tuple[RetrievalCandidate, ...]:
    merged: dict[int, RetrievalCandidate] = {}
    for candidates in candidate_groups:
        for candidate in candidates:
            existing = merged.get(candidate.chunk_id)
            if existing is None:
                merged[candidate.chunk_id] = candidate
                continue
            merged[candidate.chunk_id] = _merge_candidate(existing, candidate)
    return tuple(merged.values())


def _merge_candidate(
    left: RetrievalCandidate,
    right: RetrievalCandidate,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=left.chunk_id,
        chunk_text=left.chunk_text,
        category=left.category,
        source_uri=left.source_uri,
        source_title=left.source_title,
        source_locator=left.source_locator,
        vector_score=_max_optional(left.vector_score, right.vector_score),
        keyword_score=_max_optional(left.keyword_score, right.keyword_score),
    )


def _max_optional(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _vector_candidate_from_row(row: tuple[Any, ...]) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=int(row[0]),
        chunk_text=str(row[1]),
        category=cast(KnowledgeCategory, str(row[2])),
        source_uri=str(row[3]),
        source_title=str(row[4]),
        source_locator=_optional_text(row[5]),
        vector_score=float(row[6]),
    )


def _keyword_candidate_from_row(row: tuple[Any, ...]) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=int(row[0]),
        chunk_text=str(row[1]),
        category=cast(KnowledgeCategory, str(row[2])),
        source_uri=str(row[3]),
        source_title=str(row[4]),
        source_locator=_optional_text(row[5]),
        keyword_score=float(row[6]),
    )


def _format_vector(embedding: tuple[float, ...]) -> str:
    if not embedding:
        raise RetrievalStoreError("query embedding must not be empty")
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetrievalConfigurationError(f"{field_name} must be set")
    return value.strip()


def _require_score(value: float, field_name: str) -> float:
    if not isinstance(value, float) or not 0 <= value <= 1:
        raise RetrievalConfigurationError(f"{field_name} must be between 0 and 1")
    return value
