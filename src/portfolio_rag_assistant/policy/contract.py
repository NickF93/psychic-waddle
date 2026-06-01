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
QuestionIntent = Literal[
    "workplace",
    "current_role",
    "skills",
    "education",
    "publications",
    "projects",
    "contact",
]

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


@dataclass(frozen=True, slots=True)
class _IntentRule:
    category: KnowledgeCategory
    trigger_groups: tuple[frozenset[str], ...]
    evidence_groups: tuple[frozenset[str], ...]


_INTENT_RULES: dict[QuestionIntent, _IntentRule] = {
    "workplace": _IntentRule(
        category="experience",
        trigger_groups=(
            frozenset(
                (
                    "where",
                    "dove",
                    "company",
                    "companies",
                    "employer",
                    "employers",
                    "workplace",
                    "workplaces",
                )
            ),
            frozenset(
                (
                    "work",
                    "worked",
                    "works",
                    "working",
                    "lavorato",
                    "lavora",
                    "company",
                    "companies",
                    "employer",
                    "employers",
                    "workplace",
                    "workplaces",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "workplace",
                    "workplaces",
                    "worked",
                    "works",
                    "currently",
                    "previously",
                    "employer",
                    "employers",
                    "company",
                    "companies",
                    "history",
                    "internship",
                    "internships",
                    "role",
                    "roles",
                )
            ),
        ),
    ),
    "current_role": _IntentRule(
        category="experience",
        trigger_groups=(
            frozenset(
                (
                    "current",
                    "currently",
                    "now",
                    "present",
                    "today",
                )
            ),
            frozenset(
                (
                    "role",
                    "title",
                    "position",
                    "ruolo",
                )
            ),
        ),
        evidence_groups=(
            frozenset(("current", "currently", "since", "serves", "lead", "technical")),
            frozenset(("role", "title", "position", "engineer", "researcher", "lead")),
        ),
    ),
    "skills": _IntentRule(
        category="skills",
        trigger_groups=(
            frozenset(
                (
                    "skill",
                    "skills",
                    "stack",
                    "technology",
                    "technologies",
                    "tool",
                    "tools",
                    "framework",
                    "frameworks",
                    "competenze",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "skill",
                    "skills",
                    "technology",
                    "technologies",
                    "tool",
                    "tools",
                    "framework",
                    "frameworks",
                    "language",
                    "languages",
                    "uses",
                    "include",
                    "includes",
                )
            ),
        ),
    ),
    "education": _IntentRule(
        category="education",
        trigger_groups=(
            frozenset(
                (
                    "education",
                    "degree",
                    "degrees",
                    "phd",
                    "master",
                    "bachelor",
                    "university",
                    "studied",
                    "study",
                    "formazione",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "education",
                    "degree",
                    "degrees",
                    "phd",
                    "master",
                    "bachelor",
                    "university",
                    "studied",
                    "completed",
                )
            ),
        ),
    ),
    "publications": _IntentRule(
        category="research",
        trigger_groups=(
            frozenset(
                (
                    "publication",
                    "publications",
                    "paper",
                    "papers",
                    "doi",
                    "arxiv",
                    "thesis",
                    "pubblicazioni",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "publication",
                    "publications",
                    "published",
                    "paper",
                    "papers",
                    "doi",
                    "arxiv",
                    "thesis",
                    "research",
                    "submitted",
                    "released",
                )
            ),
        ),
    ),
    "projects": _IntentRule(
        category="projects",
        trigger_groups=(
            frozenset(
                (
                    "project",
                    "projects",
                    "repository",
                    "repositories",
                    "repo",
                    "repos",
                    "software",
                    "code",
                    "progetti",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "project",
                    "projects",
                    "repository",
                    "repositories",
                    "repo",
                    "repos",
                    "software",
                    "code",
                    "github",
                    "implementation",
                    "source",
                )
            ),
        ),
    ),
    "contact": _IntentRule(
        category="contact",
        trigger_groups=(
            frozenset(
                (
                    "contact",
                    "reach",
                    "linkedin",
                    "website",
                    "profile",
                    "profiles",
                    "orcid",
                    "portfolio",
                    "link",
                    "links",
                    "github",
                    "contatto",
                )
            ),
        ),
        evidence_groups=(
            frozenset(
                (
                    "contact",
                    "linkedin",
                    "website",
                    "profile",
                    "profiles",
                    "orcid",
                    "portfolio",
                    "link",
                    "links",
                    "github",
                    "public",
                )
            ),
        ),
    ),
}

_PROJECT_CONTEXT_WORDS = frozenset(
    (
        "project",
        "projects",
        "repository",
        "repositories",
        "repo",
        "repos",
        "software",
        "code",
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

        question_intents = _infer_question_intents(request.question)
        question_categories = _question_categories(
            question=request.question,
            intents=question_intents,
        )
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

        if question_intents:
            approved_context = _contexts_with_intent_support(
                approved_context,
                question_intents,
            )
            if not approved_context:
                return _not_answerable("insufficient_intent_support")

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


def _infer_question_intents(question: str) -> tuple[QuestionIntent, ...]:
    words = _normalized_words(question)
    intents: list[QuestionIntent] = []
    for intent, rule in _INTENT_RULES.items():
        if not _word_groups_match(words, rule.trigger_groups):
            continue
        if intent == "contact" and "github" in words and words & _PROJECT_CONTEXT_WORDS:
            continue
        intents.append(intent)
    return tuple(intents)


def _question_categories(
    *,
    question: str,
    intents: tuple[QuestionIntent, ...],
) -> tuple[KnowledgeCategory, ...]:
    if intents:
        return tuple(
            dict.fromkeys(_INTENT_RULES[intent].category for intent in intents)
        )
    return _infer_question_categories(question)


def _contexts_with_intent_support(
    contexts: tuple[RetrievedContext, ...],
    intents: tuple[QuestionIntent, ...],
) -> tuple[RetrievedContext, ...]:
    selected: list[RetrievedContext] = []
    selected_chunk_ids: set[int] = set()
    for intent in intents:
        rule = _INTENT_RULES[intent]
        matching_contexts = tuple(
            context
            for context in contexts
            if context.category == rule.category
            and _context_matches_intent(context, rule)
        )
        if not matching_contexts:
            return ()
        for context in matching_contexts:
            if context.chunk_id in selected_chunk_ids:
                continue
            selected.append(context)
            selected_chunk_ids.add(context.chunk_id)
    return tuple(selected)


def _context_matches_intent(context: RetrievedContext, rule: _IntentRule) -> bool:
    return _word_groups_match(
        _normalized_words(context.chunk_text),
        rule.evidence_groups,
    )


def _word_groups_match(
    words: frozenset[str],
    groups: tuple[frozenset[str], ...],
) -> bool:
    return all(words & group for group in groups)


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
