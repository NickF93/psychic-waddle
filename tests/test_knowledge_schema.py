from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

KNOWLEDGE_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_knowledge_schema.sql"
)
EMBEDDING_HASH_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0003_embedding_content_hash.sql"
)
KNOWLEDGE_MIGRATION_SQL = KNOWLEDGE_MIGRATION_PATH.read_text(encoding="utf-8")
EMBEDDING_HASH_MIGRATION_SQL = EMBEDDING_HASH_MIGRATION_PATH.read_text(
    encoding="utf-8"
)
NORMALIZED_SQL = re.sub(r"\s+", " ", KNOWLEDGE_MIGRATION_SQL.lower())
NORMALIZED_EMBEDDING_HASH_SQL = re.sub(
    r"\s+",
    " ",
    EMBEDDING_HASH_MIGRATION_SQL.lower(),
)
KNOWLEDGE_CATEGORIES = (
    "experience",
    "education",
    "projects",
    "research",
    "skills",
    "contact",
)
EMBEDDING_BACKENDS = ("ollama", "llama-cpp", "openai-compatible")


def test_migration_enables_pgvector() -> None:
    assert "create extension if not exists vector;" in NORMALIZED_SQL


def test_embedding_hash_migration_enables_pgcrypto() -> None:
    assert "create extension if not exists pgcrypto;" in NORMALIZED_EMBEDDING_HASH_SQL


def test_migration_defines_knowledge_authority_tables() -> None:
    for table_name in ("sources", "facts", "chunks", "chunk_embeddings"):
        assert f"create table {table_name} (" in NORMALIZED_SQL


def test_facts_require_source_and_public_visibility() -> None:
    facts_block = _table_block("facts")

    assert (
        "source_id bigint not null references sources(id) on delete restrict"
        in facts_block
    )
    assert "public_visible boolean not null default false" in facts_block
    assert "constraint facts_source_category_text_unique unique" in facts_block


def test_chunks_require_source_and_public_visibility() -> None:
    chunks_block = _table_block("chunks")

    assert (
        "source_id bigint not null references sources(id) on delete restrict"
        in chunks_block
    )
    assert "public_visible boolean not null default false" in chunks_block
    assert "chunk_index integer not null" in chunks_block
    assert "constraint chunks_source_index_unique unique" in chunks_block


@pytest.mark.parametrize("table_name", ("facts", "chunks"))
def test_facts_and_chunks_use_bounded_categories(table_name: str) -> None:
    table_block = _table_block(table_name)

    for category in KNOWLEDGE_CATEGORIES:
        assert f"'{category}'" in table_block
    assert "category text not null" in table_block
    assert f"constraint {table_name}_category_allowed check" in table_block


def test_chunk_embeddings_are_separated_by_backend_and_model() -> None:
    embeddings_block = _table_block("chunk_embeddings")

    assert "chunk_id bigint not null references chunks(id) on delete cascade" in (
        embeddings_block
    )
    assert "embedding_backend text not null" in embeddings_block
    assert "embedding_model text not null" in embeddings_block
    assert "embedding_dimension integer not null" in embeddings_block
    assert "embedding vector not null" in embeddings_block
    for backend in EMBEDDING_BACKENDS:
        assert f"'{backend}'" in embeddings_block
    assert "vector_dims(embedding) = embedding_dimension" in embeddings_block
    assert (
        "constraint chunk_embeddings_chunk_backend_model_unique unique"
        in embeddings_block
    )


def test_embedding_hash_migration_requires_content_hash() -> None:
    assert "alter table chunk_embeddings add column chunk_text_hash text" in (
        NORMALIZED_EMBEDDING_HASH_SQL
    )
    assert "alter column chunk_text_hash set not null" in (
        NORMALIZED_EMBEDDING_HASH_SQL
    )
    assert "constraint chunk_embeddings_text_hash_sha256 check" in (
        NORMALIZED_EMBEDDING_HASH_SQL
    )
    assert "digest(convert_to(chunks.chunk_text, 'utf8'), 'sha256')" in (
        NORMALIZED_EMBEDDING_HASH_SQL
    )


def test_schema_does_not_define_retrieval_indexes_yet() -> None:
    assert " using hnsw " not in NORMALIZED_SQL
    assert " using ivfflat " not in NORMALIZED_SQL
    assert "tsvector" not in NORMALIZED_SQL


def test_migration_applies_to_postgresql_when_database_url_is_set() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set")
    if shutil.which("psql") is None:
        pytest.fail("TEST_DATABASE_URL is set but psql is not available")

    schema_name = f"knowledge_schema_test_{uuid.uuid4().hex}"
    _run_psql(database_url, f'CREATE SCHEMA "{schema_name}";')
    try:
        _run_psql(
            database_url,
            f"""
            SET search_path TO "{schema_name}", public;

            {KNOWLEDGE_MIGRATION_SQL}

            INSERT INTO sources (source_uri, title, reviewed_at)
            VALUES ('file://cv', 'Curated CV', now());

            INSERT INTO facts (
                source_id,
                category,
                fact_text,
                public_visible
            )
            SELECT id, 'experience', 'Niccolo worked at NAIS s.r.l.', true
            FROM sources
            WHERE source_uri = 'file://cv';

            INSERT INTO chunks (
                source_id,
                category,
                chunk_index,
                chunk_text,
                public_visible
            )
            SELECT id, 'experience', 0, 'Niccolo worked at NAIS s.r.l.', true
            FROM sources
            WHERE source_uri = 'file://cv';

            INSERT INTO chunk_embeddings (
                chunk_id,
                embedding_backend,
                embedding_model,
                embedding_dimension,
                embedding
            )
            SELECT id, 'ollama', 'nomic-embed-text', 3, '[0.1,0.2,0.3]'::vector
            FROM chunks
            WHERE chunk_index = 0;

            {EMBEDDING_HASH_MIGRATION_SQL}

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM chunk_embeddings
                    WHERE chunk_text_hash = encode(
                        digest(
                            convert_to('Niccolo worked at NAIS s.r.l.', 'UTF8'),
                            'sha256'
                        ),
                        'hex'
                    )
                ) THEN
                    RAISE EXCEPTION 'embedding hash migration did not backfill';
                END IF;
            END $$;
            """,
        )
    finally:
        _run_psql(
            database_url,
            f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;',
            check=False,
        )


def _table_block(table_name: str) -> str:
    pattern = rf"create table {table_name} \((.*?)\);"
    match = re.search(pattern, NORMALIZED_SQL)
    if match is None:
        pytest.fail(f"{table_name} table not found in migration")
    return match.group(1)


def _run_psql(database_url: str, sql: str, *, check: bool = True) -> None:
    result = subprocess.run(
        ("psql", "--set", "ON_ERROR_STOP=1", "--dbname", database_url, "--command", sql),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and result.returncode != 0:
        pytest.fail(
            "psql migration command failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
