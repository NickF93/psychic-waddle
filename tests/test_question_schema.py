from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
QUESTION_MIGRATION_PATH = MIGRATIONS_DIR / "0002_question_events.sql"
QUESTION_MIGRATION_SQL = QUESTION_MIGRATION_PATH.read_text(encoding="utf-8")
ALL_MIGRATION_SQL = "\n\n".join(
    path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
)
NORMALIZED_SQL = re.sub(r"\s+", " ", QUESTION_MIGRATION_SQL.lower())
QUESTION_STATES = ("pending", "reviewed", "ignored")
QUESTION_CATEGORIES = (
    "missing_fact",
    "alias",
    "eval_case",
    "unclear",
    "off_topic",
    "private_data",
    "spam",
    "other",
)
FORBIDDEN_COLUMNS = (
    "ip",
    "user_agent",
    "cookie",
    "session",
    "frontend",
    "language",
    "answer",
    "status_code",
    "source",
    "score",
    "retrieval",
    "metadata",
)


def test_question_event_schema_defines_review_queue() -> None:
    table_block = _table_block("question_events")

    assert "raw_question_text text not null" in table_block
    assert "review_state text not null default 'pending'" in table_block
    assert "review_category text" in table_block
    assert "review_note text" in table_block
    assert "created_at timestamptz not null default now()" in table_block
    assert "updated_at timestamptz not null default now()" in table_block
    assert "question_events_raw_question_text_not_blank" in table_block


def test_question_event_schema_uses_bounded_review_values() -> None:
    table_block = _table_block("question_events")

    for state in QUESTION_STATES:
        assert f"'{state}'" in table_block
    for category in QUESTION_CATEGORIES:
        assert f"'{category}'" in table_block
    assert "question_events_review_state_allowed" in table_block
    assert "question_events_review_category_allowed" in table_block


def test_question_event_schema_excludes_runtime_visitor_metadata() -> None:
    table_block = _table_block("question_events")

    for forbidden_column in FORBIDDEN_COLUMNS:
        assert forbidden_column not in table_block


def test_question_event_schema_adds_review_indexes() -> None:
    assert "create index question_events_review_state_idx" in NORMALIZED_SQL
    assert "create index question_events_created_at_idx" in NORMALIZED_SQL


def test_all_migrations_apply_to_postgresql_when_database_url_is_set() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set")
    if shutil.which("psql") is None:
        pytest.fail("TEST_DATABASE_URL is set but psql is not available")

    schema_name = f"question_schema_test_{uuid.uuid4().hex}"
    _run_psql(database_url, f'CREATE SCHEMA "{schema_name}";')
    try:
        _run_psql(
            database_url,
            f"""
            SET search_path TO "{schema_name}", public;

            {ALL_MIGRATION_SQL}

            INSERT INTO question_events (raw_question_text)
            VALUES ('What did Niccolo do at a company I heard about?');

            UPDATE question_events
            SET review_state = 'reviewed',
                review_category = 'missing_fact',
                review_note = 'Needs a reviewed source before any KB change.',
                updated_at = now()
            WHERE id = 1;
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
