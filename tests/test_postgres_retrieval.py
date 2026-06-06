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

from intent_catalog_helpers import tracked_intent_catalog
from portfolio_rag_assistant.intent import SemanticIntentResolver
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
    retriever = _retriever(
        connection=connection,
        provider=provider,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="Where did Niccolo work?", top_k=2))
    )

    assert provider.embedding_requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("Where did Niccolo work?",)),
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=_semantic_anchor_questions(),
        ),
    )
    assert provider.chat_requests == ()
    assert tuple(result.chunk_id for result in response.results) == (1, 3)
    assert response.results[0].score.combined_score == pytest.approx(1.0)
    assert response.results[0].score.vector_score == 0.72
    assert response.results[0].score.keyword_score == 0.9
    assert response.results[1].score.combined_score == pytest.approx(
        ((1 / 62) + (1 / 61)) / (2 / 61)
    )
    assert response.results[1].score.vector_score is None
    assert response.results[1].score.keyword_score == 0.5


@pytest.mark.parametrize(
    "question",
    (
        "Is Niccolo a good fit for industrial computer vision roles?",
        "Is Niccolo a strong match for industrial machine vision work?",
    ),
)
def test_postgres_retriever_returns_fit_experience_and_skills_context(
    question: str,
) -> None:
    experience = _row(
        1,
        (
            "experience: Niccolo Ferrari's professional experience as a Senior "
            "Machine Learning Engineer and Researcher focuses on industrial "
            "computer vision."
        ),
        0.95,
        category="experience",
        source_locator="About me",
    )
    skills = _row(
        2,
        (
            "skills: Niccolo Ferrari's main technical skills combine "
            "industrial computer vision, anomaly detection, segmentation, C++ "
            "inference, Python, PyTorch, TensorFlow, Halcon, OpenCV, ONNX, "
            "OpenVINO, TensorRT, and Docker."
        ),
        0.94,
        category="skills",
        source_locator="Professional Skills",
    )
    connection = FakeRetrievalConnection(
        vector_rows=(experience, skills),
        keyword_rows=(),
        intent_rows=(experience, skills),
    )
    provider = FakeEmbeddingProvider(((1.0, 0.0),))
    retriever = _retriever(connection=connection, provider=provider)

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question=question, top_k=4))
    )

    assert tuple(
        intent.identifier for intent in response.intent_resolution.required_intents
    ) == (
        "professional_overview",
        "skills",
    )
    contexts_by_category = {context.category: context for context in response.results}
    assert contexts_by_category["experience"].score.combined_score >= 0.7
    assert contexts_by_category["skills"].score.combined_score >= 0.7


def test_postgres_retriever_queries_only_public_backend_model_chunks() -> None:
    connection = FakeRetrievalConnection(vector_rows=(), keyword_rows=())
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
        embedding_backend="openai-compatible",
        embedding_model="text-embedding-3-small",
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
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
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
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
    )

    response = asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=2)))

    assert tuple(result.chunk_id for result in response.results) == (1, 2)
    assert response.results[0].score.combined_score < (
        response.results[1].score.combined_score
    )
    assert response.results[0].score.vector_score == 0.4
    assert response.results[0].score.keyword_score == 0.1


def test_postgres_retriever_threshold_score_ignores_missing_optional_channels() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(
            _row(1, "experience: Niccolo worked at NAIS s.r.l.", 0.72),
        ),
        keyword_rows=(
            _row(1, "experience: Niccolo worked at NAIS s.r.l.", 0.9),
        ),
        intent_rows=(
            _row(2, "experience: weaker intent-only workplace context", 0.8),
        ),
    )
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="Where did Niccolo work?", top_k=2))
    )

    assert response.results[0].chunk_id == 1
    assert response.results[0].score.combined_score >= 0.7


def test_postgres_retriever_does_not_apply_policy_score_threshold() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(
            _row(1, "experience: vector-only candidate for policy review", 0.05),
        ),
        keyword_rows=(),
    )
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="NAIS", top_k=1))
    )

    assert tuple(result.chunk_id for result in response.results) == (1,)
    assert response.results[0].score.combined_score == pytest.approx(1.0)


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
    provider = FakeEmbeddingProvider(((0.1, 0.2),))
    retriever = _retriever(
        connection=connection,
        provider=provider,
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


def test_postgres_retriever_uses_candidate_intents_for_retrieval_only() -> None:
    connection = FakeRetrievalConnection(
        vector_rows=(),
        keyword_rows=(),
        intent_rows=(
            _row(
                9,
                (
                    "skills: Niccolo Ferrari's technical skills include "
                    "industrial computer vision and anomaly detection."
                ),
                0.75,
            ),
        ),
    )
    provider = FakeEmbeddingProvider(
        ((1.0, 0.0),),
        semantic_anchor_embedding=(1.0, 0.0),
    )
    retriever = _retriever(connection=connection, provider=provider)

    response = asyncio.run(
        retriever.retrieve(
            RetrievalRequest(
                question="Which technical strengths would he bring?",
                top_k=4,
            )
        )
    )

    assert response.intent_resolution.required_intents == ()
    assert response.intent_resolution.candidate_intents
    assert tuple(result.chunk_id for result in response.results) == (9,)
    intent_query, intent_params = connection.calls[2]
    assert "WITH intent_query" in intent_query
    assert "skills" in intent_params[1]


def test_postgres_retriever_rejects_invalid_configuration() -> None:
    provider = FakeEmbeddingProvider(((1.0,),))
    with pytest.raises(RetrievalConfigurationError):
        PostgreSQLRetriever(
            connection=FakeRetrievalConnection(vector_rows=(), keyword_rows=()),
            provider=provider,
            embedding_backend=" ",
            embedding_model="model",
            intent_resolver=SemanticIntentResolver(
                catalog=tracked_intent_catalog(),
                provider=provider,
                embedding_model="model",
            ),
        )


def test_postgres_retriever_rejects_wrong_embedding_count() -> None:
    retriever = _retriever(
        connection=FakeRetrievalConnection(vector_rows=(), keyword_rows=()),
        provider=FakeEmbeddingProvider(((1.0,), (2.0,))),
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
    provider = FakeEmbeddingProvider(((1.0, 0.0),))
    retriever = _retriever(
        connection=db_connection,
        provider=provider,
    )

    response = asyncio.run(retriever.retrieve(RetrievalRequest(question="NAIS", top_k=1)))

    assert len(response.results) == 1
    assert response.results[0].chunk_text == "experience: Niccolo worked at NAIS s.r.l."
    assert response.results[0].source_uri == "cv://niccolo/main"


def test_postgres_retriever_retrieves_workplace_aggregate_for_natural_question(
    db_connection: object,
) -> None:
    db_connection.execute(
        """
        INSERT INTO sources (source_uri, title, reviewed_at)
        VALUES ('cv://niccolo/main', 'Niccolo Ferrari CV', now())
        """
    )
    source_id = db_connection.execute(
        "SELECT id FROM sources WHERE source_uri = 'cv://niccolo/main'"
    ).fetchone()[0]
    chunk_rows = (
        (
            "experience",
            0,
            "Niccolo Ferrari's Ph.D. work resulted in two publications.",
            "Professional Experience",
        ),
        (
            "experience",
            1,
            "During Ph.D. work, Niccolo Ferrari designed two Python architectures.",
            "Professional Experience",
        ),
        (
            "skills",
            2,
            "Niccolo Ferrari uses MLflow and TensorBoard for experiment tracking.",
            "Frameworks, Ecosystems and Tools",
        ),
        (
            "experience",
            3,
            "Niccolo Ferrari works between applied research and production software.",
            "About me",
        ),
        (
            "experience",
            4,
            (
                "Niccolo Ferrari's professional workplaces include NAIS S.r.l. "
                "in Bologna, Bonfiglioli Engineering in Ferrara, the University "
                "of Ferrara, and CIAS in Ferrara."
            ),
            "Professional Experience",
        ),
        (
            "experience",
            5,
            (
                "Niccolo Ferrari's work history includes Senior Machine Learning "
                "Engineer and Researcher at NAIS S.r.l. and Machine Learning "
                "Engineer at Bonfiglioli Engineering."
            ),
            "Professional Experience",
        ),
    )
    for category, chunk_index, chunk_text, source_locator in chunk_rows:
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
            VALUES (%s, %s, %s, %s, %s, true)
            """,
            (source_id, category, chunk_index, chunk_text, source_locator),
        )
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
        SELECT
            id,
            'ollama',
            'nomic-embed-text',
            encode(digest(convert_to(chunk_text, 'UTF8'), 'sha256'), 'hex'),
            2,
            '[1,0]'::vector
        FROM chunks
        """
    )
    db_connection.commit()
    provider = FakeEmbeddingProvider(((1.0, 0.0),))
    retriever = _retriever(
        connection=db_connection,
        provider=provider,
    )

    response = asyncio.run(
        retriever.retrieve(RetrievalRequest(question="Where did Niccolo work?", top_k=4))
    )

    retrieved_text = "\n".join(result.chunk_text for result in response.results)
    assert "professional workplaces include NAIS S.r.l." in retrieved_text
    assert "Bonfiglioli Engineering" in retrieved_text


def _row(
    chunk_id: int,
    chunk_text: str,
    score: float,
    *,
    category: str = "experience",
    source_locator: str = "Experience section",
) -> tuple[object, ...]:
    return (
        chunk_id,
        chunk_text,
        category,
        "cv://niccolo/main",
        "Niccolo Ferrari CV",
        source_locator,
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
    def __init__(
        self,
        embeddings: tuple[tuple[float, ...], ...],
        *,
        semantic_anchor_embedding: tuple[float, ...] | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._semantic_anchor_embedding = semantic_anchor_embedding
        self.embedding_requests: tuple[EmbeddingRequest, ...] = ()
        self.chat_requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        raise AssertionError("retrieval must not call chat")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.embedding_requests = (*self.embedding_requests, request)
        if len(self.embedding_requests) == 1:
            embeddings = self._embeddings
        else:
            anchor_embedding = self._semantic_anchor_embedding
            if anchor_embedding is None:
                anchor_embedding = tuple(-value for value in self._embeddings[0])
            embeddings = tuple(
                anchor_embedding
                for _input in request.inputs
            )
        return EmbeddingResponse(model=request.model, embeddings=embeddings)


def _retriever(
    *,
    connection: Any,
    provider: FakeEmbeddingProvider,
    embedding_backend: str = "ollama",
    embedding_model: str = "nomic-embed-text",
) -> PostgreSQLRetriever:
    return PostgreSQLRetriever(
        connection=connection,
        provider=provider,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        intent_resolver=SemanticIntentResolver(
            catalog=tracked_intent_catalog(),
            provider=provider,
            embedding_model=embedding_model,
        ),
    )


def _semantic_anchor_questions() -> tuple[str, ...]:
    return tuple(
        question
        for profile in tracked_intent_catalog().profiles
        for question in profile.semantic_example_questions
    )
