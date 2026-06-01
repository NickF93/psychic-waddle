"""Bounded recruiter-question intent profiles."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from portfolio_rag_assistant.knowledge import (
    ALLOWED_KNOWLEDGE_CATEGORIES,
    KnowledgeCategory,
)

QuestionIntent = Literal[
    "workplace",
    "current_role",
    "skills",
    "education",
    "publications",
    "projects",
    "contact",
]


class QuestionIntentProfileError(Exception):
    """Raised when a question intent profile violates its bounded contract."""


@dataclass(frozen=True, slots=True)
class QuestionIntentProfile:
    """Deterministic vocabulary for one supported recruiter question intent."""

    intent: QuestionIntent
    accepted_categories: tuple[KnowledgeCategory, ...]
    trigger_groups: tuple[frozenset[str], ...]
    lexical_expansion_terms: frozenset[str]
    required_evidence_groups: tuple[frozenset[str], ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.intent, "intent")
        _require_non_empty_tuple(self.accepted_categories, "accepted_categories")
        _require_non_empty_tuple(self.trigger_groups, "trigger_groups")
        _require_non_empty_terms(
            self.lexical_expansion_terms,
            "lexical_expansion_terms",
        )
        _require_non_empty_tuple(
            self.required_evidence_groups,
            "required_evidence_groups",
        )
        for category in self.accepted_categories:
            if category not in ALLOWED_KNOWLEDGE_CATEGORIES:
                allowed = ", ".join(sorted(ALLOWED_KNOWLEDGE_CATEGORIES))
                raise QuestionIntentProfileError(
                    f"accepted_categories must contain only: {allowed}"
                )
        for field_name, groups in (
            ("trigger_groups", self.trigger_groups),
            ("required_evidence_groups", self.required_evidence_groups),
        ):
            for group in groups:
                _require_non_empty_terms(group, field_name)


def _word_groups_match(
    words: frozenset[str],
    groups: tuple[frozenset[str], ...],
) -> bool:
    return all(words & group for group in groups)


def _normalized_words(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return frozenset(re.findall(r"[a-z0-9]+", ascii_text))


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty string")


def _require_non_empty_tuple(value: tuple[object, ...], field_name: str) -> None:
    if not isinstance(value, tuple) or not value:
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty tuple")


def _require_non_empty_terms(value: frozenset[str], field_name: str) -> None:
    if not isinstance(value, frozenset) or not value:
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty frozenset")
    for term in value:
        _require_non_empty_text(term, field_name)


QUESTION_INTENT_PROFILES: tuple[QuestionIntentProfile, ...] = (
    QuestionIntentProfile(
        intent="workplace",
        accepted_categories=("experience",),
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
                    "employed",
                    "workplace",
                    "workplaces",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "company",
                "companies",
                "employer",
                "employers",
                "employment",
                "work",
                "worked",
                "workplace",
                "workplaces",
                "work history",
            )
        ),
        required_evidence_groups=(
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
    QuestionIntentProfile(
        intent="current_role",
        accepted_categories=("experience",),
        trigger_groups=(
            frozenset(("current", "currently", "now", "present", "today")),
            frozenset(
                (
                    "role",
                    "title",
                    "position",
                    "ruolo",
                    "employs",
                    "employer",
                    "company",
                    "works",
                    "work",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "current",
                "current employer",
                "current role",
                "currently",
                "employer",
                "position",
                "role",
                "title",
            )
        ),
        required_evidence_groups=(
            frozenset(("current", "currently", "since", "serves", "lead", "technical")),
            frozenset(("role", "title", "position", "engineer", "researcher", "lead")),
        ),
    ),
    QuestionIntentProfile(
        intent="skills",
        accepted_categories=("skills",),
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
        lexical_expansion_terms=frozenset(
            (
                "frameworks",
                "languages",
                "machine learning",
                "ml",
                "skills",
                "stack",
                "technologies",
                "tools",
            )
        ),
        required_evidence_groups=(
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
    QuestionIntentProfile(
        intent="education",
        accepted_categories=("education",),
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
        lexical_expansion_terms=frozenset(
            (
                "bachelor",
                "degree",
                "degrees",
                "education",
                "master",
                "phd",
                "study",
                "university",
            )
        ),
        required_evidence_groups=(
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
    QuestionIntentProfile(
        intent="publications",
        accepted_categories=("research",),
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
        lexical_expansion_terms=frozenset(
            (
                "arxiv",
                "doi",
                "paper",
                "papers",
                "publication",
                "publications",
                "research",
                "thesis",
            )
        ),
        required_evidence_groups=(
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
    QuestionIntentProfile(
        intent="projects",
        accepted_categories=("projects",),
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
        lexical_expansion_terms=frozenset(
            (
                "code",
                "github",
                "project",
                "projects",
                "repositories",
                "repository",
                "research software",
                "software",
                "source",
            )
        ),
        required_evidence_groups=(
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
    QuestionIntentProfile(
        intent="contact",
        accepted_categories=("contact",),
        trigger_groups=(
            frozenset(
                (
                    "contact",
                    "reach",
                    "linkedin",
                    "website",
                    "orcid",
                    "portfolio",
                    "link",
                    "links",
                    "github",
                    "contatto",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "github",
                "linkedin",
                "links",
                "orcid",
                "portfolio",
                "profile",
                "profiles",
                "public",
                "website",
            )
        ),
        required_evidence_groups=(
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
)

_PROFILES_BY_INTENT: dict[QuestionIntent, QuestionIntentProfile] = {
    profile.intent: profile for profile in QUESTION_INTENT_PROFILES
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


def detect_question_intents(question: str) -> tuple[QuestionIntent, ...]:
    """Return supported recruiter intents that match a question."""

    _require_non_empty_text(question, "question")
    words = _normalized_words(question)
    intents: list[QuestionIntent] = []
    for profile in QUESTION_INTENT_PROFILES:
        if not _word_groups_match(words, profile.trigger_groups):
            continue
        if (
            profile.intent == "contact"
            and "github" in words
            and words & _PROJECT_CONTEXT_WORDS
        ):
            continue
        intents.append(profile.intent)
    return tuple(intents)


def profile_for_intent(intent: QuestionIntent) -> QuestionIntentProfile:
    """Return the immutable profile for one supported intent."""

    try:
        return _PROFILES_BY_INTENT[intent]
    except KeyError as error:
        raise QuestionIntentProfileError(f"unsupported question intent: {intent}") from error


def categories_for_intents(
    intents: tuple[QuestionIntent, ...],
) -> tuple[KnowledgeCategory, ...]:
    """Return accepted knowledge categories for detected intents in stable order."""

    categories: list[KnowledgeCategory] = []
    for intent in intents:
        for category in profile_for_intent(intent).accepted_categories:
            if category not in categories:
                categories.append(category)
    return tuple(categories)


def text_satisfies_intent_evidence(text: str, intent: QuestionIntent) -> bool:
    """Return whether text contains the required evidence terms for an intent."""

    _require_non_empty_text(text, "text")
    profile = profile_for_intent(intent)
    return _word_groups_match(
        _normalized_words(text),
        profile.required_evidence_groups,
    )

