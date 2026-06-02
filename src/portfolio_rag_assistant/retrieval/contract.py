"""Provider-neutral retrieval contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from portfolio_rag_assistant.knowledge import (
    ALLOWED_KNOWLEDGE_CATEGORIES,
    KnowledgeCategory,
)


class RetrievalError(Exception):
    """Base error for retrieval-owned failures."""


class RetrievalConfigurationError(RetrievalError):
    """Raised when retrieval is configured incorrectly."""


class RetrievalRequestError(RetrievalError):
    """Raised when a retrieval request cannot satisfy the contract."""


class RetrievalStoreError(RetrievalError):
    """Raised when reviewed knowledge cannot be searched."""


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """Question and result limit for retrieving reviewed context."""

    question: str
    top_k: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.question, "question")
        if not _is_positive_int(self.top_k):
            raise ValueError("top_k must be a positive integer")


@dataclass(frozen=True, slots=True)
class RetrievalScore:
    """Inspectable score metadata for one retrieved chunk."""

    combined_score: float
    vector_score: float | None = None
    keyword_score: float | None = None

    def __post_init__(self) -> None:
        _require_non_negative_float(self.combined_score, "combined_score")
        _require_optional_non_negative_float(self.vector_score, "vector_score")
        _require_optional_non_negative_float(self.keyword_score, "keyword_score")


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """Public source-backed chunk returned by retrieval."""

    chunk_id: int
    chunk_text: str
    category: KnowledgeCategory
    source_uri: str
    source_title: str
    score: RetrievalScore
    source_locator: str | None = None
    public_visible: bool = True

    def __post_init__(self) -> None:
        if not _is_positive_int(self.chunk_id):
            raise ValueError("chunk_id must be a positive integer")
        _require_non_empty_text(self.chunk_text, "chunk_text")
        if self.category not in ALLOWED_KNOWLEDGE_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_KNOWLEDGE_CATEGORIES))
            raise ValueError(f"category must be one of: {allowed}")
        _require_non_empty_text(self.source_uri, "source_uri")
        _require_non_empty_text(self.source_title, "source_title")
        if not isinstance(self.score, RetrievalScore):
            raise ValueError("score must be a RetrievalScore")
        if self.source_locator is not None:
            _require_non_empty_text(self.source_locator, "source_locator")
        if self.public_visible is not True:
            raise ValueError("retrieved context must be public_visible")


@dataclass(frozen=True, slots=True)
class RetrievalResponse:
    """Ranked retrieved context for one question."""

    question: str
    results: tuple[RetrievedContext, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.question, "question")
        _require_tuple_of_type(self.results, RetrievedContext, "results")


@runtime_checkable
class Retriever(Protocol):
    """Retrieval authority for search, ranking, and diagnostics only."""

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """Return ranked public source-backed context for a question."""


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _is_positive_int(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _require_non_negative_float(value: float, field_name: str) -> None:
    if not isinstance(value, float) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative float")


def _require_optional_non_negative_float(
    value: float | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_non_negative_float(value, field_name)


def _require_tuple_of_type(
    values: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    if not all(isinstance(value, item_type) for value in values):
        raise ValueError(f"{field_name} must contain only {item_type.__name__}")
