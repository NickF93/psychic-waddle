"""Curated fact input contract for verified knowledge."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias, cast

KnowledgeCategory: TypeAlias = Literal[
    "experience",
    "education",
    "projects",
    "research",
    "skills",
    "contact",
]

CURRENT_KNOWLEDGE_SCHEMA_VERSION = 1

ALLOWED_KNOWLEDGE_CATEGORIES: frozenset[str] = frozenset(
    ("experience", "education", "projects", "research", "skills", "contact")
)

_TOP_LEVEL_KEYS = frozenset(("schema_version", "sources", "facts"))
_SOURCE_KEYS = frozenset(("source_uri", "title", "reviewed_at"))
_FACT_KEYS = frozenset(
    ("source_uri", "category", "fact_text", "source_locator", "public_visible")
)
_REQUIRED_FACT_KEYS = frozenset(("source_uri", "category", "fact_text", "public_visible"))
_FORBIDDEN_VISITOR_KEYS = frozenset(
    (
        "visitor_question",
        "visitor_questions",
        "question",
        "questions",
        "question_text",
        "raw_transcript",
        "transcript",
        "ip",
        "ip_address",
        "user_agent",
        "cookie",
        "cookies",
        "session_id",
        "email",
        "phone",
        "photo",
    )
)


class KnowledgeInputError(ValueError):
    """Raised when curated knowledge input violates the public contract."""


@dataclass(frozen=True, slots=True)
class SourceInput:
    """Reviewed source admitted into the curated knowledge input."""

    source_uri: str
    title: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_uri", _require_text(self.source_uri, "source_uri"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        if not isinstance(self.reviewed_at, datetime):
            raise KnowledgeInputError("reviewed_at must be a datetime")
        _require_timezone_aware(self.reviewed_at, "reviewed_at")


@dataclass(frozen=True, slots=True)
class FactInput:
    """Atomic reviewed public-profile claim tied to one source."""

    source_uri: str
    category: KnowledgeCategory
    fact_text: str
    public_visible: bool
    source_locator: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_uri", _require_text(self.source_uri, "source_uri"))
        category = _require_text(self.category, "category")
        if category not in ALLOWED_KNOWLEDGE_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_KNOWLEDGE_CATEGORIES))
            raise KnowledgeInputError(f"category must be one of: {allowed}")
        object.__setattr__(self, "category", cast(KnowledgeCategory, category))
        object.__setattr__(self, "fact_text", _require_text(self.fact_text, "fact_text"))
        if not isinstance(self.public_visible, bool):
            raise KnowledgeInputError("public_visible must be an explicit boolean")
        if self.source_locator is not None:
            object.__setattr__(
                self,
                "source_locator",
                _require_text(self.source_locator, "source_locator"),
            )


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Complete curated knowledge input document."""

    schema_version: int
    sources: tuple[SourceInput, ...]
    facts: tuple[FactInput, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version != CURRENT_KNOWLEDGE_SCHEMA_VERSION
        ):
            raise KnowledgeInputError(
                f"schema_version must be {CURRENT_KNOWLEDGE_SCHEMA_VERSION}"
            )
        _require_non_empty_tuple(self.sources, SourceInput, "sources")
        if not isinstance(self.facts, tuple):
            raise KnowledgeInputError("facts must be a tuple")
        if not all(isinstance(fact, FactInput) for fact in self.facts):
            raise KnowledgeInputError("facts must contain only FactInput records")
        _require_unique_source_uris(self.sources)
        _require_known_fact_sources(self.sources, self.facts)


def parse_knowledge_document(data: object) -> KnowledgeDocument:
    """Parse and validate one JSON-compatible curated knowledge document."""

    document = _require_mapping(data, "document")
    _reject_forbidden_keys(document, "document")
    _require_allowed_keys(document, _TOP_LEVEL_KEYS, "document")
    _require_required_keys(document, _TOP_LEVEL_KEYS, "document")

    schema_version = _require_int(document["schema_version"], "schema_version")
    sources = tuple(
        _parse_source(record, f"sources[{index}]")
        for index, record in enumerate(_require_records(document["sources"], "sources"))
    )
    facts = tuple(
        _parse_fact(record, f"facts[{index}]")
        for index, record in enumerate(_require_records(document["facts"], "facts"))
    )

    return KnowledgeDocument(
        schema_version=schema_version,
        sources=sources,
        facts=facts,
    )


def _parse_source(record: object, field_name: str) -> SourceInput:
    source = _require_mapping(record, field_name)
    _reject_forbidden_keys(source, field_name)
    _require_allowed_keys(source, _SOURCE_KEYS, field_name)
    _require_required_keys(source, _SOURCE_KEYS, field_name)

    return SourceInput(
        source_uri=_require_text(source["source_uri"], f"{field_name}.source_uri"),
        title=_require_text(source["title"], f"{field_name}.title"),
        reviewed_at=_parse_reviewed_at(
            source["reviewed_at"],
            f"{field_name}.reviewed_at",
        ),
    )


def _parse_fact(record: object, field_name: str) -> FactInput:
    fact = _require_mapping(record, field_name)
    _reject_forbidden_keys(fact, field_name)
    _require_allowed_keys(fact, _FACT_KEYS, field_name)
    _require_required_keys(fact, _REQUIRED_FACT_KEYS, field_name)

    return FactInput(
        source_uri=_require_text(fact["source_uri"], f"{field_name}.source_uri"),
        category=cast(
            KnowledgeCategory,
            _require_text(fact["category"], f"{field_name}.category"),
        ),
        fact_text=_require_text(fact["fact_text"], f"{field_name}.fact_text"),
        source_locator=_parse_optional_text(
            fact.get("source_locator"),
            f"{field_name}.source_locator",
        ),
        public_visible=_require_bool(
            fact["public_visible"],
            f"{field_name}.public_visible",
        ),
    )


def _reject_forbidden_keys(record: Mapping[object, object], field_name: str) -> None:
    keys = {str(key) for key in record}
    forbidden = sorted(keys & _FORBIDDEN_VISITOR_KEYS)
    if forbidden:
        names = ", ".join(forbidden)
        raise KnowledgeInputError(f"{field_name} contains forbidden visitor data: {names}")


def _require_allowed_keys(
    record: Mapping[object, object],
    allowed_keys: frozenset[str],
    field_name: str,
) -> None:
    keys = {str(key) for key in record}
    unknown = sorted(keys - allowed_keys)
    if unknown:
        names = ", ".join(unknown)
        raise KnowledgeInputError(f"{field_name} contains unsupported fields: {names}")


def _require_required_keys(
    record: Mapping[object, object],
    required_keys: frozenset[str],
    field_name: str,
) -> None:
    keys = {str(key) for key in record}
    missing = sorted(required_keys - keys)
    if missing:
        names = ", ".join(missing)
        raise KnowledgeInputError(f"{field_name} is missing required fields: {names}")


def _require_mapping(value: object, field_name: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise KnowledgeInputError(f"{field_name} must be an object")
    return value


def _require_records(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise KnowledgeInputError(f"{field_name} must be an array")
    if len(value) == 0:
        raise KnowledgeInputError(f"{field_name} must not be empty")
    return value


def _require_non_empty_tuple(
    value: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(value, tuple) or len(value) == 0:
        raise KnowledgeInputError(f"{field_name} must be a non-empty tuple")
    if not all(isinstance(item, item_type) for item in value):
        raise KnowledgeInputError(f"{field_name} must contain only {item_type.__name__}")


def _require_unique_source_uris(sources: tuple[SourceInput, ...]) -> None:
    seen: set[str] = set()
    for source in sources:
        if source.source_uri in seen:
            raise KnowledgeInputError(f"duplicate source_uri: {source.source_uri}")
        seen.add(source.source_uri)


def _require_known_fact_sources(
    sources: tuple[SourceInput, ...],
    facts: tuple[FactInput, ...],
) -> None:
    known_source_uris = {source.source_uri for source in sources}
    for fact in facts:
        if fact.source_uri not in known_source_uris:
            raise KnowledgeInputError(f"fact references unknown source_uri: {fact.source_uri}")


def _require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KnowledgeInputError(f"{field_name} must be an integer")
    return value


def _require_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise KnowledgeInputError(f"{field_name} must be an explicit boolean")
    return value


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeInputError(f"{field_name} must be a non-empty string")
    return value.strip()


def _parse_optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _parse_reviewed_at(value: object, field_name: str) -> datetime:
    text = _require_text(value, field_name)
    normalized = text.removesuffix("Z") + "+00:00" if text.endswith("Z") else text
    try:
        reviewed_at = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise KnowledgeInputError(f"{field_name} must be an ISO 8601 timestamp") from error
    _require_timezone_aware(reviewed_at, field_name)
    return reviewed_at


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KnowledgeInputError(f"{field_name} must include a timezone")
