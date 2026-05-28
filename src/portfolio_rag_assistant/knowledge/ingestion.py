"""Offline ingestion planning for curated public-profile knowledge."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from portfolio_rag_assistant.knowledge.input import (
    FactInput,
    KnowledgeDocument,
    KnowledgeInputError,
    SourceInput,
    parse_knowledge_document,
)


class KnowledgeIngestionError(ValueError):
    """Raised when curated knowledge cannot be ingested deterministically."""


@dataclass(frozen=True, slots=True)
class KnowledgeBatch:
    """Validated set of curated sources and facts loaded for one ingestion run."""

    sources: tuple[SourceInput, ...]
    facts: tuple[FactInput, ...]

    def __post_init__(self) -> None:
        if not self.sources:
            raise KnowledgeIngestionError("ingestion requires at least one source")
        _require_unique_sources(self.sources)
        _require_unique_facts(self.facts)
        _require_known_fact_sources(self.sources, self.facts)


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """Deterministic chunk derived from one public fact."""

    source_uri: str
    category: str
    chunk_index: int
    chunk_text: str
    source_locator: str | None
    public_visible: bool


def load_knowledge_batch(paths: Sequence[Path | str]) -> KnowledgeBatch:
    """Load and validate one or more curated JSON files."""

    if not paths:
        raise KnowledgeIngestionError("at least one curated JSON file is required")
    documents = tuple(load_knowledge_document(Path(path)) for path in paths)
    return knowledge_batch_from_documents(documents)


def load_knowledge_document(path: Path) -> KnowledgeDocument:
    """Load one curated JSON file through the accepted input contract."""

    if path.suffix.lower() != ".json":
        raise KnowledgeIngestionError(f"{path}: only curated JSON files are supported")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise KnowledgeIngestionError(f"{path}: cannot read curated file") from error
    except json.JSONDecodeError as error:
        raise KnowledgeIngestionError(f"{path}: invalid JSON") from error

    try:
        return parse_knowledge_document(payload)
    except KnowledgeInputError as error:
        raise KnowledgeIngestionError(f"{path}: {error}") from error


def knowledge_batch_from_documents(
    documents: Iterable[KnowledgeDocument],
) -> KnowledgeBatch:
    """Combine validated documents into one ingestion batch."""

    sources: list[SourceInput] = []
    facts: list[FactInput] = []
    for document in documents:
        sources.extend(document.sources)
        facts.extend(document.facts)
    return KnowledgeBatch(sources=tuple(sources), facts=tuple(facts))


def build_fact_chunks(batch: KnowledgeBatch) -> tuple[KnowledgeChunk, ...]:
    """Create one stable chunk for each public fact in a batch."""

    chunks: list[KnowledgeChunk] = []
    seen_indexes: dict[tuple[str, int], KnowledgeChunk] = {}
    for fact in batch.facts:
        if not fact.public_visible:
            continue
        chunk = KnowledgeChunk(
            source_uri=fact.source_uri,
            category=fact.category,
            chunk_index=stable_chunk_index(fact),
            chunk_text=f"{fact.category}: {fact.fact_text}",
            source_locator=fact.source_locator,
            public_visible=True,
        )
        key = (chunk.source_uri, chunk.chunk_index)
        existing = seen_indexes.get(key)
        if existing is not None and existing.chunk_text != chunk.chunk_text:
            raise KnowledgeIngestionError(
                f"chunk_index collision for source_uri {chunk.source_uri}"
            )
        seen_indexes[key] = chunk
        chunks.append(chunk)
    return tuple(chunks)


def stable_chunk_index(fact: FactInput) -> int:
    """Return a deterministic positive integer identifier for a fact chunk."""

    digest = hashlib.blake2s(
        f"{fact.category}\0{fact.fact_text}".encode("utf-8"),
        digest_size=4,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=False) & 0x7FFFFFFF


def _require_unique_sources(sources: tuple[SourceInput, ...]) -> None:
    seen: set[str] = set()
    for source in sources:
        if source.source_uri in seen:
            raise KnowledgeIngestionError(f"duplicate source_uri: {source.source_uri}")
        seen.add(source.source_uri)


def _require_unique_facts(facts: tuple[FactInput, ...]) -> None:
    seen: set[tuple[str, str, str]] = set()
    for fact in facts:
        key = (fact.source_uri, fact.category, fact.fact_text)
        if key in seen:
            raise KnowledgeIngestionError(
                f"duplicate fact for source_uri {fact.source_uri}: {fact.fact_text}"
            )
        seen.add(key)


def _require_known_fact_sources(
    sources: tuple[SourceInput, ...],
    facts: tuple[FactInput, ...],
) -> None:
    source_uris = {source.source_uri for source in sources}
    for fact in facts:
        if fact.source_uri not in source_uris:
            raise KnowledgeIngestionError(
                f"fact references unknown source_uri: {fact.source_uri}"
            )
