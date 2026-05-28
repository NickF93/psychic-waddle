from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from portfolio_rag_assistant.knowledge import (
    CURRENT_KNOWLEDGE_SCHEMA_VERSION,
    FactInput,
    KnowledgeInputError,
    SourceInput,
    parse_knowledge_document,
)


def valid_document() -> dict[str, Any]:
    return {
        "schema_version": CURRENT_KNOWLEDGE_SCHEMA_VERSION,
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


def test_parse_knowledge_document_accepts_source_backed_public_fact() -> None:
    document = parse_knowledge_document(valid_document())

    assert document.schema_version == CURRENT_KNOWLEDGE_SCHEMA_VERSION
    assert document.sources == (
        SourceInput(
            source_uri="cv://niccolo/main",
            title="Niccolo Ferrari CV",
            reviewed_at=datetime(2026, 5, 28, tzinfo=UTC),
        ),
    )
    assert document.facts == (
        FactInput(
            source_uri="cv://niccolo/main",
            category="experience",
            fact_text="Niccolo worked at NAIS s.r.l.",
            source_locator="Experience section",
            public_visible=True,
        ),
    )


def test_parse_knowledge_document_rejects_fact_without_source() -> None:
    data = valid_document()
    data["facts"][0]["source_uri"] = "cv://niccolo/missing"

    with pytest.raises(KnowledgeInputError, match="unknown source_uri"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_rejects_unsupported_category() -> None:
    data = valid_document()
    data["facts"][0]["category"] = "hobbies"

    with pytest.raises(KnowledgeInputError, match="category must be one of"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_requires_explicit_public_visibility() -> None:
    data = valid_document()
    del data["facts"][0]["public_visible"]

    with pytest.raises(KnowledgeInputError, match="public_visible"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_rejects_duplicate_sources() -> None:
    data = valid_document()
    data["sources"].append(dict(data["sources"][0]))

    with pytest.raises(KnowledgeInputError, match="duplicate source_uri"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_rejects_visitor_question_fields() -> None:
    data = valid_document()
    data["visitor_questions"] = ["Where did Niccolo work?"]

    with pytest.raises(KnowledgeInputError, match="forbidden visitor data"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_rejects_timezone_naive_review_timestamp() -> None:
    data = valid_document()
    data["sources"][0]["reviewed_at"] = "2026-05-28T00:00:00"

    with pytest.raises(KnowledgeInputError, match="timezone"):
        parse_knowledge_document(data)


def test_parse_knowledge_document_rejects_implicit_boolean_values() -> None:
    data = valid_document()
    data["facts"][0]["public_visible"] = 1

    with pytest.raises(KnowledgeInputError, match="explicit boolean"):
        parse_knowledge_document(data)
