"""PostgreSQL retrieval over verified public knowledge."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol, cast

from portfolio_rag_assistant.intent import (
    IntentCatalog,
    QuestionIntent,
    SemanticIntentResolver,
)
from portfolio_rag_assistant.knowledge import KnowledgeCategory
from portfolio_rag_assistant.provider import EmbeddingProvider, EmbeddingRequest
from portfolio_rag_assistant.retrieval.contract import (
    RetrievedContext,
    RetrievalConfigurationError,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalScore,
    RetrievalStoreError,
)

_RRF_RANK_CONSTANT = 60.0


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
    intent_score: float | None = None
    vector_rank: int | None = None
    keyword_rank: int | None = None
    intent_rank: int | None = None
    rrf_order_score: float = 0.0
    rank_quality_score: float = 0.0

    @property
    def combined_score(self) -> float:
        return self.rank_quality_score

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
        provider: EmbeddingProvider,
        embedding_backend: str,
        embedding_model: str,
        intent_resolver: SemanticIntentResolver,
        candidate_fan_out: int,
    ) -> None:
        self._connection = connection
        self._provider = provider
        self._embedding_backend = _require_text(embedding_backend, "embedding_backend")
        self._embedding_model = _require_text(embedding_model, "embedding_model")
        self._candidate_fan_out = _require_positive_int(
            candidate_fan_out,
            "candidate_fan_out",
        )
        if not isinstance(intent_resolver, SemanticIntentResolver):
            raise RetrievalConfigurationError(
                "intent_resolver must be SemanticIntentResolver"
            )
        self._intent_resolver = intent_resolver

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """Return ranked public source-backed context for a question."""

        embedding_response = await self._provider.embed(
            EmbeddingRequest(model=self._embedding_model, inputs=(request.question,))
        )
        if len(embedding_response.embeddings) != 1:
            raise RetrievalStoreError("provider returned the wrong embedding count")

        question_embedding = embedding_response.embeddings[0]
        intent_resolution = await self._intent_resolver.resolve(
            question=request.question,
            question_embedding=question_embedding,
        )
        vector_candidates = self._search_vectors(
            query_embedding=question_embedding,
            limit=self._candidate_fan_out,
        )
        keyword_candidates = self._search_keywords(
            question=request.question,
            limit=self._candidate_fan_out,
        )
        intent_candidates = self._search_intent_keywords(
            intents=intent_resolution.retrieval_intents,
            limit=self._candidate_fan_out,
        )
        results = tuple(
            candidate.to_context()
            for candidate in _rank_candidates(
                vector_candidates=vector_candidates,
                keyword_candidates=keyword_candidates,
                intent_candidates=intent_candidates,
                top_k=request.top_k,
            )
        )
        return RetrievalResponse(
            question=request.question,
            results=results,
            intent_resolution=intent_resolution,
        )

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
                SELECT websearch_to_tsquery('english', %s) AS value
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
                        to_tsvector('english', chunks.chunk_text),
                        keyword_query.value
                    )::double precision
                ) AS keyword_score
            FROM chunks
            JOIN sources ON sources.id = chunks.source_id
            CROSS JOIN keyword_query
            WHERE chunks.public_visible = true
              AND to_tsvector('english', chunks.chunk_text) @@ keyword_query.value
            ORDER BY keyword_score DESC, chunks.id ASC
            LIMIT %s
            """,
            (question, limit),
        )
        return tuple(_keyword_candidate_from_row(row) for row in cursor.fetchall())

    def _search_intent_keywords(
        self,
        *,
        intents: tuple[QuestionIntent, ...],
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        if not intents:
            return ()

        cursor = self._connection.execute(
            """
            WITH intent_query AS (
                SELECT websearch_to_tsquery('english', %s) AS value
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
                        to_tsvector('english', chunks.chunk_text),
                        intent_query.value
                    )::double precision
                ) AS intent_score
            FROM chunks
            JOIN sources ON sources.id = chunks.source_id
            CROSS JOIN intent_query
            WHERE chunks.public_visible = true
              AND chunks.category = ANY(%s::text[])
              AND to_tsvector('english', chunks.chunk_text) @@ intent_query.value
            ORDER BY intent_score DESC, chunks.id ASC
            LIMIT %s
            """,
            (
                _intent_evidence_query_text(
                    intents=intents,
                    intent_catalog=self._intent_resolver.catalog,
                ),
                list(self._intent_resolver.catalog.categories_for_intents(intents)),
                limit,
            ),
        )
        return tuple(_intent_candidate_from_row(row) for row in cursor.fetchall())


def _rank_candidates(
    *,
    vector_candidates: tuple[RetrievalCandidate, ...],
    keyword_candidates: tuple[RetrievalCandidate, ...],
    intent_candidates: tuple[RetrievalCandidate, ...],
    top_k: int,
) -> tuple[RetrievalCandidate, ...]:
    candidates = tuple(
        _with_rrf_score(candidate)
        for candidate in _merge_candidates(
            _ranked_vector_candidates(vector_candidates),
            _ranked_keyword_candidates(keyword_candidates),
            _ranked_intent_candidates(intent_candidates),
        )
    )
    return tuple(
        candidate
        for candidate in sorted(
            candidates,
            key=lambda item: (
                -item.rrf_order_score,
                -(item.vector_score or 0.0),
                -(item.keyword_score or 0.0),
                -(item.intent_score or 0.0),
                item.chunk_id,
            ),
        )
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
        intent_score=_max_optional(left.intent_score, right.intent_score),
        vector_rank=_min_optional(left.vector_rank, right.vector_rank),
        keyword_rank=_min_optional(left.keyword_rank, right.keyword_rank),
        intent_rank=_min_optional(left.intent_rank, right.intent_rank),
        rrf_order_score=max(left.rrf_order_score, right.rrf_order_score),
        rank_quality_score=max(left.rank_quality_score, right.rank_quality_score),
    )


def _max_optional(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _min_optional(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _ranked_vector_candidates(
    candidates: tuple[RetrievalCandidate, ...],
) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        replace(candidate, vector_rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    )


def _ranked_keyword_candidates(
    candidates: tuple[RetrievalCandidate, ...],
) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        replace(candidate, keyword_rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    )


def _ranked_intent_candidates(
    candidates: tuple[RetrievalCandidate, ...],
) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        replace(candidate, intent_rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    )


def _with_rrf_score(candidate: RetrievalCandidate) -> RetrievalCandidate:
    matched_ranks = _matched_channel_ranks(candidate)
    if not matched_ranks:
        return candidate
    order_score = sum(_rrf_contribution(rank=rank) for rank in matched_ranks)
    max_rank_quality_score = len(matched_ranks) * _rrf_contribution(rank=1)
    return replace(
        candidate,
        rrf_order_score=order_score,
        rank_quality_score=min(1.0, order_score / max_rank_quality_score),
    )


def _matched_channel_ranks(candidate: RetrievalCandidate) -> tuple[int, ...]:
    return tuple(
        rank
        for rank in (
            candidate.vector_rank,
            candidate.keyword_rank,
            candidate.intent_rank,
        )
        if rank is not None
    )


def _rrf_contribution(*, rank: int) -> float:
    return 1.0 / (_RRF_RANK_CONSTANT + rank)


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


def _intent_candidate_from_row(row: tuple[Any, ...]) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=int(row[0]),
        chunk_text=str(row[1]),
        category=cast(KnowledgeCategory, str(row[2])),
        source_uri=str(row[3]),
        source_title=str(row[4]),
        source_locator=_optional_text(row[5]),
        intent_score=float(row[6]),
    )


def _intent_evidence_query_text(
    intents: tuple[QuestionIntent, ...],
    intent_catalog: IntentCatalog,
) -> str:
    terms: list[str] = []
    seen_terms: set[str] = set()
    for intent in intents:
        profile = intent_catalog.profile_for_intent(intent)
        for term in sorted(profile.lexical_expansion_terms):
            formatted_term = _format_websearch_intent_term(term)
            term_key = formatted_term.casefold()
            if term_key in seen_terms:
                continue
            terms.append(formatted_term)
            seen_terms.add(term_key)
    return " OR ".join(terms)


def _format_websearch_intent_term(term: str) -> str:
    cleaned_term = " ".join(term.split())
    if not cleaned_term:
        raise RetrievalConfigurationError(
            "intent lexical expansion terms must not be blank"
        )
    if '"' in cleaned_term:
        raise RetrievalConfigurationError(
            "intent lexical expansion terms must not contain double quotes"
        )
    if " " in cleaned_term:
        return f'"{cleaned_term}"'
    return cleaned_term


def _format_vector(embedding: tuple[float, ...]) -> str:
    if not embedding:
        raise RetrievalStoreError("query embedding must not be empty")
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _require_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RetrievalConfigurationError(f"{field_name} must be a positive integer")
    if value <= 0:
        raise RetrievalConfigurationError(f"{field_name} must be a positive integer")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetrievalConfigurationError(f"{field_name} must be set")
    return value.strip()
