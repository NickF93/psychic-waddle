from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from portfolio_rag_assistant import cli


def test_ingest_command_validates_input_before_database_connection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [],
                "facts": [],
            }
        ),
        encoding="utf-8",
    )
    called = False

    def fail_connect_database(database_url: str) -> object:
        nonlocal called
        called = True
        raise AssertionError(database_url)

    monkeypatch.setattr(cli, "connect_database", fail_connect_database)
    stderr = StringIO()

    exit_code = cli.run(
        ("knowledge", "ingest", str(invalid_path)),
        env={"DATABASE_URL": "postgresql://example"},
        stderr=stderr,
    )

    assert exit_code == 2
    assert called is False
    assert "sources must not be empty" in stderr.getvalue()


def test_validate_command_does_not_require_database_or_provider_config(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.run(
        ("knowledge", "validate", str(valid_path)),
        env={},
        stdout=stdout,
    )

    assert exit_code == 0
    assert "validated 1 sources, 1 facts, 1 chunks" in stdout.getvalue()


def test_ingest_command_requires_database_url_after_valid_input(tmp_path: Path) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stderr = StringIO()

    exit_code = cli.run(("knowledge", "ingest", str(valid_path)), env={}, stderr=stderr)

    assert exit_code == 2
    assert "DATABASE_URL must be set" in stderr.getvalue()


def _valid_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sources": [
            {
                "source_uri": "cv://niccolo/main",
                "title": "Niccolo Ferrari CV",
                "reviewed_at": "2026-05-28T00:00:00+00:00",
            }
        ],
        "facts": [
            {
                "source_uri": "cv://niccolo/main",
                "category": "experience",
                "fact_text": "Niccolo worked at NAIS s.r.l.",
                "source_locator": "Experience section",
                "public_visible": True,
            }
        ],
    }
