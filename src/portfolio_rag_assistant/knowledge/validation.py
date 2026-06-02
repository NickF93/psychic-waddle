"""Deterministic QA checks for curated knowledge files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from portfolio_rag_assistant.knowledge.ingestion import (
    KnowledgeBatch,
    KnowledgeIngestionError,
    build_fact_chunks,
    load_knowledge_batch,
)


class KnowledgeValidationError(ValueError):
    """Raised when curated knowledge fails deterministic QA checks."""


@dataclass(frozen=True, slots=True)
class KnowledgeValidationReport:
    """Successful validation result for curated knowledge."""

    source_count: int
    fact_count: int
    public_fact_count: int
    chunk_count: int


def validate_knowledge_files(paths: Sequence[Path | str]) -> KnowledgeValidationReport:
    """Validate curated JSON files without mutating external state."""

    try:
        batch = load_knowledge_batch(paths)
    except KnowledgeIngestionError as error:
        raise KnowledgeValidationError(str(error)) from error
    return validate_knowledge_batch(batch)


def validate_knowledge_batch(batch: KnowledgeBatch) -> KnowledgeValidationReport:
    """Run local QA checks on an already parsed knowledge batch."""

    _require_each_source_has_facts(batch)
    public_fact_count = _require_public_facts(batch)
    chunks = build_fact_chunks(batch)
    if len(chunks) != public_fact_count:
        raise KnowledgeValidationError("every public fact must produce one chunk")
    for chunk in chunks:
        if not chunk.public_visible:
            raise KnowledgeValidationError("generated chunks must be public")
        if not chunk.chunk_text.strip():
            raise KnowledgeValidationError("generated chunk text must not be empty")

    return KnowledgeValidationReport(
        source_count=len(batch.sources),
        fact_count=len(batch.facts),
        public_fact_count=public_fact_count,
        chunk_count=len(chunks),
    )


def _require_each_source_has_facts(batch: KnowledgeBatch) -> None:
    source_uris_with_facts = {fact.source_uri for fact in batch.facts}
    for source in batch.sources:
        if source.source_uri not in source_uris_with_facts:
            raise KnowledgeValidationError(
                f"source has no facts: {source.source_uri}"
            )


def _require_public_facts(batch: KnowledgeBatch) -> int:
    public_fact_count = sum(1 for fact in batch.facts if fact.public_visible)
    if public_fact_count == 0:
        raise KnowledgeValidationError("knowledge must contain at least one public fact")
    return public_fact_count
