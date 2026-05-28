from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfolio_rag_assistant.knowledge import (
    FactInput,
    KnowledgeBatch,
    KnowledgeChunk,
    KnowledgeValidationError,
    SourceInput,
    validate_knowledge_batch,
    validate_knowledge_files,
)
from portfolio_rag_assistant.knowledge import validation


def test_validate_knowledge_batch_accepts_valid_minimal_knowledge() -> None:
    report = validate_knowledge_batch(_batch())

    assert report.source_count == 1
    assert report.fact_count == 1
    assert report.public_fact_count == 1
    assert report.chunk_count == 1


def test_validate_knowledge_batch_rejects_source_without_facts() -> None:
    batch = KnowledgeBatch(
        sources=(
            _source("cv://niccolo/main"),
            _source("portfolio://pigreco/work"),
        ),
        facts=(_fact("cv://niccolo/main"),),
    )

    with pytest.raises(KnowledgeValidationError, match="source has no facts"):
        validate_knowledge_batch(batch)


def test_validate_knowledge_batch_rejects_no_public_facts() -> None:
    batch = _batch(public_visible=False)

    with pytest.raises(KnowledgeValidationError, match="public fact"):
        validate_knowledge_batch(batch)


def test_validate_knowledge_batch_rejects_invalid_generated_chunks(monkeypatch) -> None:
    def invalid_chunks(batch: KnowledgeBatch) -> tuple[KnowledgeChunk, ...]:
        return (
            KnowledgeChunk(
                source_uri="cv://niccolo/main",
                category="experience",
                chunk_index=1,
                chunk_text="experience: Niccolo worked at NAIS s.r.l.",
                source_locator=None,
                public_visible=False,
            ),
        )

    monkeypatch.setattr(validation, "build_fact_chunks", invalid_chunks)

    with pytest.raises(KnowledgeValidationError, match="public"):
        validate_knowledge_batch(_batch())


def test_validate_knowledge_files_rejects_duplicate_facts(tmp_path: Path) -> None:
    data = _valid_json()
    data["facts"].append(dict(data["facts"][0]))
    path = _write_json(tmp_path, data)

    with pytest.raises(KnowledgeValidationError, match="duplicate fact"):
        validate_knowledge_files((path,))


def test_validate_knowledge_files_rejects_missing_source_reference(
    tmp_path: Path,
) -> None:
    data = _valid_json()
    data["facts"][0]["source_uri"] = "cv://niccolo/missing"
    path = _write_json(tmp_path, data)

    with pytest.raises(KnowledgeValidationError, match="unknown source_uri"):
        validate_knowledge_files((path,))


def test_validate_knowledge_files_rejects_visitor_data(tmp_path: Path) -> None:
    data = _valid_json()
    data["visitor_questions"] = ["Where did Niccolo work?"]
    path = _write_json(tmp_path, data)

    with pytest.raises(KnowledgeValidationError, match="forbidden visitor data"):
        validate_knowledge_files((path,))


def _batch(*, public_visible: bool = True) -> KnowledgeBatch:
    return KnowledgeBatch(
        sources=(_source("cv://niccolo/main"),),
        facts=(_fact("cv://niccolo/main", public_visible=public_visible),),
    )


def _source(source_uri: str) -> SourceInput:
    return SourceInput(
        source_uri=source_uri,
        title="Niccolo Ferrari CV",
        reviewed_at=datetime(2026, 5, 28, tzinfo=UTC),
    )


def _fact(source_uri: str, *, public_visible: bool = True) -> FactInput:
    return FactInput(
        source_uri=source_uri,
        category="experience",
        fact_text="Niccolo worked at NAIS s.r.l.",
        source_locator="Experience section",
        public_visible=public_visible,
    )


def _valid_json() -> dict[str, object]:
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


def _write_json(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
