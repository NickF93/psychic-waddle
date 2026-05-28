from __future__ import annotations

import importlib.util
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfolio_rag_assistant.knowledge import (
    FactInput,
    KnowledgeBatch,
    KnowledgeStore,
    SourceInput,
)

MIGRATION_SQL = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_knowledge_schema.sql"
).read_text(encoding="utf-8")


@pytest.fixture
def db_connection() -> Iterator[object]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set")
    if importlib.util.find_spec("psycopg") is None:
        pytest.skip("psycopg is not installed")

    import psycopg

    schema_name = f"offline_ingestion_test_{uuid.uuid4().hex}"
    with psycopg.connect(database_url, autocommit=True) as admin_connection:
        admin_connection.execute(f'CREATE SCHEMA "{schema_name}"')
        try:
            with psycopg.connect(database_url) as connection:
                connection.execute(f'SET search_path TO "{schema_name}", public')
                connection.execute(MIGRATION_SQL)
                connection.commit()
                yield connection
        finally:
            admin_connection.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


def test_ingestion_persists_sources_facts_and_chunks(db_connection: object) -> None:
    KnowledgeStore(db_connection).ingest_batch(
        _batch("Niccolo worked at NAIS s.r.l.", public_visible=True)
    )

    assert _count(db_connection, "sources") == 1
    assert _count(db_connection, "facts") == 1
    assert _count(db_connection, "chunks") == 1


def test_ingestion_is_idempotent(db_connection: object) -> None:
    batch = _batch("Niccolo worked at NAIS s.r.l.", public_visible=True)
    store = KnowledgeStore(db_connection)

    store.ingest_batch(batch)
    store.ingest_batch(batch)

    assert _count(db_connection, "sources") == 1
    assert _count(db_connection, "facts") == 1
    assert _count(db_connection, "chunks") == 1


def test_ingestion_reconciles_only_batch_sources(db_connection: object) -> None:
    store = KnowledgeStore(db_connection)
    store.ingest_batch(_batch("Niccolo worked at NAIS s.r.l.", public_visible=True))
    store.ingest_batch(_batch("Niccolo worked at Bonfiglioli.", public_visible=True))

    fact_texts = tuple(
        row[0]
        for row in db_connection.execute(
            "SELECT fact_text FROM facts ORDER BY fact_text"
        ).fetchall()
    )

    assert fact_texts == ("Niccolo worked at Bonfiglioli.",)
    assert _count(db_connection, "chunks") == 1


def test_ingestion_does_not_chunk_non_public_facts(db_connection: object) -> None:
    KnowledgeStore(db_connection).ingest_batch(
        _batch("Private reviewed note.", public_visible=False)
    )

    assert _count(db_connection, "sources") == 1
    assert _count(db_connection, "facts") == 1
    assert _count(db_connection, "chunks") == 0


def _batch(fact_text: str, *, public_visible: bool) -> KnowledgeBatch:
    source = SourceInput(
        source_uri="cv://niccolo/main",
        title="Niccolo Ferrari CV",
        reviewed_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
    fact = FactInput(
        source_uri=source.source_uri,
        category="experience",
        fact_text=fact_text,
        source_locator="Experience section",
        public_visible=public_visible,
    )
    return KnowledgeBatch(sources=(source,), facts=(fact,))


def _count(connection: object, table_name: str) -> int:
    row = connection.execute(f"SELECT count(*) FROM {table_name}").fetchone()
    assert row is not None
    return int(row[0])
