"""Deterministic answerability policy contracts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from portfolio_rag_assistant.knowledge import (
    ALLOWED_KNOWLEDGE_CATEGORIES,
    KnowledgeCategory,
)
from portfolio_rag_assistant.retrieval import RetrievedContext

AnswerDecisionStatus = Literal["answerable", "not_answerable", "needs_clarification"]

ANSWERABLE: AnswerDecisionStatus = "answerable"
NOT_ANSWERABLE: AnswerDecisionStatus = "not_answerable"
NEEDS_CLARIFICATION: AnswerDecisionStatus = "needs_clarification"

ANSWER_POLICY_STATUSES: frozenset[str] = frozenset(
    (ANSWERABLE, NOT_ANSWERABLE, NEEDS_CLARIFICATION)
)

MINIMUM_SOURCE_COUNT = 1

_CATEGORY_KEYWORDS: dict[KnowledgeCategory, frozenset[str]] = {
    "experience": frozenset(
        (
            "career",
            "company",
            "companies",
            "employer",
            "employers",
            "experience",
            "job",
            "jobs",
            "role",
            "roles",
            "work",
            "worked",
            "working",
        )
    ),
    "education": frozenset(
        (
            "academic",
            "bachelor",
            "degree",
            "education",
            "master",
            "phd",
            "studied",
            "study",
            "thesis",
            "university",
        )
    ),
    "projects": frozenset(
        (
            "app",
            "built",
            "developed",
            "github",
            "portfolio",
            "project",
            "projects",
            "repository",
            "software",
        )
    ),
    "research": frozenset(
        (
            "experiment",
            "experiments",
            "paper",
            "publication",
            "publications",
            "research",
        )
    ),
    "skills": frozenset(
        (
            "framework",
            "frameworks",
            "language",
            "languages",
            "skill",
            "skills",
            "stack",
            "technology",
            "technologies",
            "tool",
            "tools",
        )
    ),
    "contact": frozenset(
        (
            "contact",
            "email",
            "linkedin",
            "reach",
            "website",
        )
    ),
}

_BROAD_QUESTION_KEYWORDS = frozenset(
    (
        "about",
        "background",
        "describe",
        "introduce",
        "overview",
        "profile",
        "summary",
    )
)


class AnswerPolicyError(Exception):
    """Base error for answerability policy failures."""


class AnswerPolicyRequestError(AnswerPolicyError):
    """Raised when an answerability request violates the contract."""


@dataclass(frozen=True, slots=True)
class AnswerPolicyRequest:
    """Question, retrieved context, and threshold for answerability decisions."""

    question: str
    retrieved_context: tuple[RetrievedContext, ...]
    min_score: float

    def __post_init__(self) -> None:
        _require_non_empty_text(self.question, "question")
        _require_tuple_of_type(
            self.retrieved_context,
            RetrievedContext,
            "retrieved_context",
        )
        _require_score_threshold(self.min_score, "min_score")


@dataclass(frozen=True, slots=True)
class AnswerPolicyDecision:
    """Deterministic answerability decision and approved context."""

    status: AnswerDecisionStatus
    reason: str
    approved_context: tuple[RetrievedContext, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in ANSWER_POLICY_STATUSES:
            allowed = ", ".join(sorted(ANSWER_POLICY_STATUSES))
            raise AnswerPolicyRequestError(f"status must be one of: {allowed}")
        _require_non_empty_text(self.reason, "reason")
        _require_tuple_of_type(
            self.approved_context,
            RetrievedContext,
            "approved_context",
        )
        if self.status == ANSWERABLE and not self.approved_context:
            raise AnswerPolicyRequestError(
                "answerable decisions require approved_context"
            )
        if self.status != ANSWERABLE and self.approved_context:
            raise AnswerPolicyRequestError(
                "non-answerable decisions must not include approved_context"
            )


@runtime_checkable
class AnswerPolicy(Protocol):
    """Answerability authority for deterministic decisions only."""

    def decide(self, request: AnswerPolicyRequest) -> AnswerPolicyDecision:
        """Decide whether retrieved context is enough to answer."""


class DeterministicAnswerPolicy:
    """Simple source-backed answerability policy."""

    def decide(self, request: AnswerPolicyRequest) -> AnswerPolicyDecision:
        usable_context = _contexts_at_or_above_score(
            request.retrieved_context,
            request.min_score,
        )
        if not request.retrieved_context:
            return _not_answerable("no_retrieved_context")
        if not usable_context:
            return _not_answerable("low_confidence_context")

        question_categories = _infer_question_categories(request.question)
        if question_categories:
            context_categories = {context.category for context in usable_context}
            if not set(question_categories).issubset(context_categories):
                return _not_answerable("unsupported_question_category")
            approved_context = tuple(
                context
                for context in usable_context
                if context.category in question_categories
            )
        else:
            available_categories = {context.category for context in usable_context}
            if not _is_broad_question(request.question):
                return _not_answerable("unsupported_question_category")
            if len(available_categories) > 1:
                return AnswerPolicyDecision(
                    status=NEEDS_CLARIFICATION,
                    reason="ambiguous_question",
                )
            approved_context = usable_context

        if _source_count(approved_context) < MINIMUM_SOURCE_COUNT:
            return _not_answerable("insufficient_source_support")

        return AnswerPolicyDecision(
            status=ANSWERABLE,
            reason="sufficient_source_backed_context",
            approved_context=approved_context,
        )


def _contexts_at_or_above_score(
    contexts: tuple[RetrievedContext, ...],
    min_score: float,
) -> tuple[RetrievedContext, ...]:
    return tuple(
        context for context in contexts if context.score.combined_score >= min_score
    )


def _infer_question_categories(question: str) -> tuple[KnowledgeCategory, ...]:
    words = _normalized_words(question)
    categories = tuple(
        category
        for category in sorted(ALLOWED_KNOWLEDGE_CATEGORIES)
        if words & _CATEGORY_KEYWORDS[category]
    )
    return categories


def _is_broad_question(question: str) -> bool:
    return bool(_normalized_words(question) & _BROAD_QUESTION_KEYWORDS)


def _normalized_words(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return frozenset(re.findall(r"[a-z0-9]+", ascii_text))


def _source_count(contexts: tuple[RetrievedContext, ...]) -> int:
    return len({context.source_uri for context in contexts})


def _not_answerable(reason: str) -> AnswerPolicyDecision:
    return AnswerPolicyDecision(status=NOT_ANSWERABLE, reason=reason)


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AnswerPolicyRequestError(f"{field_name} must be a non-empty string")


def _require_score_threshold(value: float, field_name: str) -> None:
    if not isinstance(value, float) or isinstance(value, bool):
        raise AnswerPolicyRequestError(f"{field_name} must be a float")
    if not 0 <= value <= 1:
        raise AnswerPolicyRequestError(f"{field_name} must be between 0 and 1")


def _require_tuple_of_type(
    values: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise AnswerPolicyRequestError(f"{field_name} must be a tuple")
    if not all(isinstance(value, item_type) for value in values):
        raise AnswerPolicyRequestError(
            f"{field_name} must contain only {item_type.__name__}"
        )
