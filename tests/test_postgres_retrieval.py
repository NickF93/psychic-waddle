from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import uuid
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from portfolio_rag_assistant.provider import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from portfolio_rag_assistant.retrieval import (
    PostgreSQLRetriever,
    RetrievalConfigurationError,
    RetrievalRequest,
    RetrievalStoreError,
)

KNOWLEDGE_MIGRATION_SQL = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_knowledge_schema.sql"
).read_text(encoding="utf-8")
EMBEDDING_HASH_MIGRATION_SQL = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0003_embedding_content_hash.sql"
).read_text(encoding="utf-8")


def test_postgres_retriever_embeds_question_and_returns_hybrid_results() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(
            _row(1, "experience: Niccolo worked at NAIS s.r.l.", 0.72),
            _row(2, "projects: unrelated project", 0.3),
        ),
        keyword_rows=(
            _row(1, "experience: Niccolo worked at NAIS s.r.l.", 0.9),
            _row(3, "experience: Niccolo worked at Bonfiglioli.", 0.5),
        ),
        intent_rows=(
            _row(3, "experience: Niccolo worked at Bonfiglioli.", 0.8),
        ),
    )
    provider = FakeEmbeddingProvider(((1.0, 0.0),))
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=provider,
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.5,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="Where did Niccolo work?", top_k=2))
    )

    assert provider.embedding_requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("Where did Niccolo work?",)),
    )
    assert provider.chat_requests == ()
    assert tuple(result.chunk_id for result in response.results) == (1, 3)
    assert response.results[0].score.combined_score == pytest.approx(2 / 3)
    assert response.results[0].score.vector_score == 0.72
    assert response.results[0].score.keyword_score == 0.9
    assert response.results[1].score.combined_score == pytest.approx(
        ((1 / 62) + (1 / 61)) / (3 / 61)
    )
    assert response.results[1].score.vector_score is None
    assert response.results[1].score.keyword_score == 0.5


def test_postgres_retriever_queries_only_public_backend_model_chunks() -> None:
    connection = FakeRetrievalConnection(vector_rows=(), keyword_rows=())
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=provider,
        embedding_backend="openai-compatible",
        embedding_model="text-embedding-3-small",
        min_score=0.0,
    )

    asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=4)))

    vector_query, vector_params = connection.calls[0]
    keyword_query, keyword_params = connection.calls[1]
    assert "chunks.public_visible = true" in vector_query
    assert "chunk_embeddings.embedding_backend = %s" in vector_query
    assert "chunk_embeddings.embedding_model = %s" in vector_query
    assert vector_params == (
        "[0.1,0.2]",
        "openai-compatible",
        "text-embedding-3-small",
        4,
    )
    assert "chunks.public_visible = true" in keyword_query
    assert "websearch_to_tsquery('english', %s)" in keyword_query
    assert "to_tsvector('english', chunks.chunk_text)" in keyword_query
    assert "plainto_tsquery" not in keyword_query
    assert "to_tsvector('simple'" not in keyword_query
    assert keyword_params == ("NAIS", 4)
    assert len(connection.calls) == 2
    assert not any(
        forbidden in query.lower()
        for query, _params in connection.calls
        for forbidden in ("insert ", "update ", "delete ")
    )


def test_postgres_retriever_uses_bounded_intent_expansion() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(),
        keyword_rows=(),
        intent_rows=(
            _row(
                7,
                (
                    "experience: Niccolo Ferrari's professional workplaces "
                    "include NAIS S.r.l. and Bonfiglioli Engineering."
                ),
                0.42,
            ),
        ),
    )
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=FakeEmbeddingProvider(((0.1, 0.2),)),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.3,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="Where did Niccolo work?", top_k=4))
    )

    assert tuple(result.chunk_id for result in response.results) == (7,)
    intent_query, intent_params = connection.calls[2]
    assert "WITH intent_query" in intent_query
    assert "chunks.public_visible = true" in intent_query
    assert "chunks.category = ANY(%s::text[])" in intent_query
    assert "websearch_to_tsquery('english', %s)" in intent_query
    assert "to_tsvector('english', chunks.chunk_text)" in intent_query
    intent_query_text = str(intent_params[0])
    assert "Where did Niccolo work?" not in intent_query_text
    assert " OR " in intent_query_text
    assert '"professional workplaces"' in intent_query_text
    assert '"work history"' in intent_query_text
    assert "employers" in intent_query_text
    assert not re.search(r'(^| OR )work($| OR )', intent_query_text)
    assert not re.search(r'(^| OR )worked($| OR )', intent_query_text)
    assert intent_params[1] == ["experience"]
    assert intent_params[2] == 4
    assert not any(
        forbidden in query.lower()
        for query, _params in connection.calls
        for forbidden in ("insert ", "update ", "delete ")
    )


def test_postgres_retriever_fuses_candidate_ranks() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(
            _row(2, "experience: high vector score but single channel", 0.99),
            _row(1, "experience: appears in both vector and keyword", 0.4),
        ),
        keyword_rows=(
            _row(1, "experience: appears in both vector and keyword", 0.1),
        ),
    )
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=FakeEmbeddingProvider(((0.1, 0.2),)),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.0,
    )

    response = asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=2)))

    assert tuple(result.chunk_id for result in response.results) == (1, 2)
    assert response.results[0].score.combined_score > (
        response.results[1].score.combined_score
    )
    assert response.results[0].score.vector_score == 0.4
    assert response.results[0].score.keyword_score == 0.1


def test_postgres_retriever_does_not_expand_unsupported_questions() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(
            _row(1, "experience: Niccolo worked at NAIS s.r.l.", 0.88),
        ),
        keyword_rows=(),
        intent_rows=(
            _row(2, "experience: should not be queried for pizza questions", 0.99),
        ),
    )
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=FakeEmbeddingProvider(((0.1, 0.2),)),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.0,
    )

    response = asyncio.run(
        retriever.retrieve(
            RetrievalRequest(
                question="What is Niccolo favorite pizza topping?",
                top_k=4,
            )
        )
    )

    assert tuple(result.chunk_id for result in response.results) == (1,)
    assert len(connection.calls) == 2
    assert not any("WITH intent_query" in query for query, _params in connection.calls)


def test_postgres_retriever_rejects_invalid_configuration() -> None:
    with pytest.raises(RetrievalConfigurationError):
        PostgreSQLRetriever(
            connection=FakeRetrievalConnection(vector_rows=(), keyword_rows=()),
            provider=FakeEmbeddingProvider(((1.0,),)),
            embedding_backend=" ",
            embedding_model="model",
            min_score=0.0,
        )


def test_postgres_retriever_rejects_wrong_embedding_count() -> None:
    retriever = PostgreSQLRetriever(
        connection=FakeRetrievalConnection(vector_rows=(), keyword_rows=()),
        provider=FakeEmbeddingProvider(((1.0,), (2.0,))),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.0,
    )

    with pytest.raises(RetrievalStoreError):
        asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=1)))


@pytest.fixture
def db_connection() -> Iterator[object]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set")
    if importlib.util.find_spec("psycopg") is None:
        pytest.skip("psycopg is not installed")

    import psycopg

    schema_name = f"postgres_retrieval_test_{uuid.uuid4().hex}"
    with psycopg.connect(database_url, autocommit=True) as admin_connection:
        admin_connection.execute(f'CREATE SCHEMA "{schema_name}"')
        try:
            with psycopg.connect(database_url) as connection:
                connection.execute(f'SET search_path TO "{schema_name}", public')
                connection.execute(KNOWLEDGE_MIGRATION_SQL)
                connection.execute(EMBEDDING_HASH_MIGRATION_SQL)
                connection.commit()
                yield connection
        finally:
            admin_connection.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


def test_postgres_retriever_can_read_real_schema(db_connection: object) -> None:
    db_connection.execute(
        """
        INSERT INTO sources (source_uri, title, reviewed_at)
        VALUES ('cv://niccolo/main', 'Niccolo Ferrari CV', now())
        """
    )
    source_id = db_connection.execute(
        "SELECT id FROM sources WHERE source_uri = 'cv://niccolo/main'"
    ).fetchone()[0]
    db_connection.execute(
        """
        INSERT INTO chunks (
            source_id,
            category,
            chunk_index,
            chunk_text,
            source_locator,
            public_visible
        )
        VALUES (
            %s,
            'experience',
            0,
            'experience: Niccolo worked at NAIS s.r.l.',
            'Experience section',
            true
        )
        """,
        (source_id,),
    )
    chunk_id = db_connection.execute("SELECT id FROM chunks").fetchone()[0]
    db_connection.execute(
        """
        INSERT INTO chunk_embeddings (
            chunk_id,
            embedding_backend,
            embedding_model,
            chunk_text_hash,
            embedding_dimension,
            embedding
        )
        VALUES (
            %s,
            'ollama',
            'nomic-embed-text',
            encode(
                digest(
                    convert_to('experience: Niccolo worked at NAIS s.r.l.', 'UTF8'),
                    'sha256'
                ),
                'hex'
            ),
            2,
            '[1,0]'::vector
        )
        """,
        (chunk_id,),
    )
    db_connection.commit()
    retriever = PostgreSQLRetriever(
        connection=db_connection,
        provider=FakeEmbeddingProvider(((1.0, 0.0),)),
        embedding_backend="ollama",
        embedding_model="nomic-embed-text",
        min_score=0.0,
    )

    response = asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=1)))

    assert len(response.results) == 1
    assert response.results[0].chunk_text == "experience: Niccolo worked at NAIS s.r.l."
    assert response.results[0].source_uri == "cv://niccolo/main"


def _row(chunk_id: int, chunk_text: str, score: float) -> tuple[object, ...]:
    return (
        chunk_id,
        chunk_text,
        "experience",
        "cv://niccolo/main",
        "Niccolo Ferrari CV",
        "Experience section",
        score,
    )


class FakeCursor:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class FakeRetrievalConnection:
    def __init__(
        self,
        *,
        vector_rows: tuple[tuple[object, ...], ...],
        keyword_rows: tuple[tuple[object, ...], ...],
        intent_rows: tuple[tuple[object, ...], ...] = (),
    ) -> None:
        self._vector_rows = vector_rows
        self._keyword_rows = keyword_rows
        self._intent_rows = intent_rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> FakeCursor:
        self.calls.append((query, tuple(params)))
        if "FROM chunk_embeddings" in query:
            return FakeCursor(self._vector_rows)
        if "WITH keyword_query" in query:
            return FakeCursor(self._keyword_rows)
        if "WITH intent_query" in query:
            return FakeCursor(self._intent_rows)
        raise AssertionError(f"unexpected query: {query}")


class FakeEmbeddingProvider:
    def __init__(self, embeddings: tuple[tuple[float, ...], ...]) -> None:
        self._embeddings = embeddings
        self.embedding_requests: tuple[EmbeddingRequest, ...] = ()
        self.chat_requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        raise AssertionError("retrieval must not call chat")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.embedding_requests = (*self.embedding_requests, request)
        return EmbeddingResponse(model=request.model, embeddings=self._embeddings)
