from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfolio_rag_assistant.knowledge import (
    FactInput,
    KnowledgeDocument,
    KnowledgeIngestionError,
    SourceInput,
    build_fact_chunks,
    knowledge_batch_from_documents,
    load_knowledge_batch,
    stable_chunk_index,
)


def test_knowledge_batch_accepts_distinct_source_documents() -> None:
    batch = knowledge_batch_from_documents(
        (
            _document("cv://niccolo/main", "Niccolo worked at NAIS s.r.l."),
            _document("portfolio://pigreco/work", "Niccolo worked at Bonfiglioli."),
        )
    )

    assert len(batch.sources) == 2
    assert len(batch.facts) == 2


def test_knowledge_batch_rejects_duplicate_sources_across_files() -> None:
    documents = (
        _document("cv://niccolo/main", "Niccolo worked at NAIS s.r.l."),
        _document("cv://niccolo/main", "Niccolo worked at Bonfiglioli."),
    )

    with pytest.raises(KnowledgeIngestionError, match="duplicate source_uri"):
        knowledge_batch_from_documents(documents)


def test_knowledge_batch_rejects_duplicate_facts() -> None:
    source = _source("cv://niccolo/main")
    fact = _fact("cv://niccolo/main", "Niccolo worked at NAIS s.r.l.")
    document = KnowledgeDocument(
        schema_version=1,
        sources=(source,),
        facts=(fact, fact),
    )

    with pytest.raises(KnowledgeIngestionError, match="duplicate fact"):
        knowledge_batch_from_documents((document,))


def test_build_fact_chunks_uses_only_public_facts() -> None:
    source = _source("cv://niccolo/main")
    public_fact = _fact("cv://niccolo/main", "Niccolo worked at NAIS s.r.l.")
    private_fact = _fact(
        "cv://niccolo/main",
        "Private note that is not intended for the portfolio.",
        public_visible=False,
    )
    batch = knowledge_batch_from_documents(
        (
            KnowledgeDocument(
                schema_version=1,
                sources=(source,),
                facts=(public_fact, private_fact),
            ),
        )
    )

    chunks = build_fact_chunks(batch)

    assert len(chunks) == 1
    assert chunks[0].chunk_text == "experience: Niccolo worked at NAIS s.r.l."
    assert chunks[0].public_visible is True


def test_stable_chunk_index_is_deterministic() -> None:
    fact = _fact("cv://niccolo/main", "Niccolo worked at NAIS s.r.l.")

    assert stable_chunk_index(fact) == stable_chunk_index(fact)


def test_load_knowledge_batch_rejects_markdown(tmp_path: Path) -> None:
    markdown_path = tmp_path / "knowledge.md"
    markdown_path.write_text("# Knowledge\n", encoding="utf-8")

    with pytest.raises(KnowledgeIngestionError, match="only curated JSON"):
        load_knowledge_batch((markdown_path,))


def _document(source_uri: str, fact_text: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        schema_version=1,
        sources=(_source(source_uri),),
        facts=(_fact(source_uri, fact_text),),
    )


def _source(source_uri: str) -> SourceInput:
    return SourceInput(
        source_uri=source_uri,
        title="Reviewed public profile source",
        reviewed_at=datetime(2026, 5, 28, tzinfo=UTC),
    )


def _fact(
    source_uri: str,
    fact_text: str,
    *,
    public_visible: bool = True,
) -> FactInput:
    return FactInput(
        source_uri=source_uri,
        category="experience",
        fact_text=fact_text,
        source_locator="Experience section",
        public_visible=public_visible,
    )
