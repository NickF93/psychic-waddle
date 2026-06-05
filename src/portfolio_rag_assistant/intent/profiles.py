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
    "professional_overview",
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


@dataclass(frozen=True, slots=True)
class IntentCatalog:
    """Reviewed deterministic vocabulary for supported recruiter intents."""

    profiles: tuple[QuestionIntentProfile, ...]
    contact_project_context_words: frozenset[str]

    def __post_init__(self) -> None:
        _require_non_empty_tuple(self.profiles, "profiles")
        for profile in self.profiles:
            if not isinstance(profile, QuestionIntentProfile):
                raise QuestionIntentProfileError(
                    "profiles must contain only QuestionIntentProfile values"
                )
        seen_intents: set[str] = set()
        for profile in self.profiles:
            if profile.intent in seen_intents:
                raise QuestionIntentProfileError(
                    f"duplicate question intent profile: {profile.intent}"
                )
            seen_intents.add(profile.intent)
        _require_non_empty_terms(
            self.contact_project_context_words,
            "contact_project_context_words",
        )

    def detect_question_intents(self, question: str) -> tuple[QuestionIntent, ...]:
        """Return supported recruiter intents that match a question."""

        _require_non_empty_text(question, "question")
        words = _normalized_words(question)
        intents: list[QuestionIntent] = []
        for profile in self.profiles:
            if not _term_groups_match(question, profile.trigger_groups):
                continue
            if (
                profile.intent == "contact"
                and "github" in words
                and words & self.contact_project_context_words
            ):
                continue
            intents.append(profile.intent)
        return tuple(intents)

    def profile_for_intent(self, intent: QuestionIntent) -> QuestionIntentProfile:
        """Return the immutable profile for one supported intent."""

        for profile in self.profiles:
            if profile.intent == intent:
                return profile
        raise QuestionIntentProfileError(f"unsupported question intent: {intent}")

    def categories_for_intents(
        self,
        intents: tuple[QuestionIntent, ...],
    ) -> tuple[KnowledgeCategory, ...]:
        """Return accepted knowledge categories for detected intents in stable order."""

        categories: list[KnowledgeCategory] = []
        for intent in intents:
            for category in self.profile_for_intent(intent).accepted_categories:
                if category not in categories:
                    categories.append(category)
        return tuple(categories)

    def text_satisfies_intent_evidence(
        self,
        text: str,
        intent: QuestionIntent,
    ) -> bool:
        """Return whether text contains the required evidence terms for an intent."""

        _require_non_empty_text(text, "text")
        profile = self.profile_for_intent(intent)
        return _term_groups_match(text, profile.required_evidence_groups)


def _term_groups_match(
    text: str,
    groups: tuple[frozenset[str], ...],
) -> bool:
    words = _normalized_words(text)
    normalized_text = _normalized_text(text)
    return all(
        any(
            _term_matches_text(
                term=term,
                words=words,
                normalized_text=normalized_text,
            )
            for term in group
        )
        for group in groups
    )


def _term_matches_text(
    *,
    term: str,
    words: frozenset[str],
    normalized_text: str,
) -> bool:
    normalized_term = _normalized_text(term)
    if not normalized_term:
        return False
    if " " not in normalized_term:
        return normalized_term in words
    return f" {normalized_term} " in f" {normalized_text} "


def _normalized_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def _normalized_words(text: str) -> frozenset[str]:
    return frozenset(_normalized_text(text).split())


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
        intent="professional_overview",
        accepted_categories=("experience",),
        trigger_groups=(
            frozenset(
                (
                    "background",
                    "career",
                    "experience",
                    "good fit for",
                    "kind of work",
                    "right person for",
                    "suitable for",
                    "type of work",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "career",
                "current role",
                "industrial computer vision",
                "professional background",
                "professional experience",
                "professional profile",
                "responsibilities",
                "role",
                "roles",
                "work experience",
                "work history",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "built",
                    "coordinates",
                    "current role",
                    "currently works",
                    "deployed",
                    "designed",
                    "engineer",
                    "internship",
                    "internships",
                    "leads",
                    "machine learning engineer",
                    "ph d research",
                    "professional experience",
                    "research background",
                    "researcher",
                    "senior machine learning engineer",
                    "technical lead",
                    "work history",
                    "worked at",
                    "works at",
                )
            ),
        ),
    ),
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
                "professional workplaces",
                "workplace",
                "workplaces",
                "work history",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "current employer",
                    "currently works",
                    "employed by",
                    "employer",
                    "employers",
                    "employment",
                    "professional workplaces",
                    "previously worked at",
                    "worked at",
                    "works at",
                    "work history",
                    "workplace",
                    "workplaces",
                    "company",
                    "companies",
                    "internship",
                    "internships",
                )
            ),
        ),
    ),
    QuestionIntentProfile(
        intent="current_role",
        accepted_categories=("experience",),
        trigger_groups=(
            frozenset(
                (
                    "adesso",
                    "attuale",
                    "current",
                    "currently",
                    "now",
                    "ora",
                    "present",
                    "ruolo attuale",
                    "today",
                )
            ),
            frozenset(
                (
                    "datore",
                    "datore di lavoro",
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
                "currently works",
                "datore di lavoro",
                "employer",
                "position",
                "role",
                "ruolo attuale",
                "senior machine learning engineer",
                "technical lead",
                "title",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "current employer",
                    "current role",
                    "currently employed",
                    "currently works",
                    "now",
                    "present position",
                    "present role",
                    "serves as",
                )
            ),
            frozenset(
                (
                    "company",
                    "employer",
                    "engineer",
                    "lead",
                    "position",
                    "researcher",
                    "role",
                    "title",
                    "works at",
                )
            ),
        ),
    ),
    QuestionIntentProfile(
        intent="skills",
        accepted_categories=("skills",),
        trigger_groups=(
            frozenset(
                (
                    "anomaly detection",
                    "skill",
                    "skills",
                    "stack",
                    "technology",
                    "technologies",
                    "tool",
                    "tools",
                    "framework",
                    "frameworks",
                    "good fit for",
                    "industrial computer vision",
                    "right person for",
                    "specialise",
                    "specialised",
                    "specialization",
                    "specializations",
                    "specialize",
                    "specialized",
                    "specialized in",
                    "suitable for",
                    "competenze",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "frameworks",
                "industrial computer vision",
                "languages",
                "machine learning",
                "ml",
                "segmentation",
                "skills",
                "stack",
                "technical skills",
                "technologies",
                "tools",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "anomaly detection",
                    "autoencoders",
                    "bash",
                    "c",
                    "c++",
                    "cnn",
                    "cnns",
                    "computer vision",
                    "deep learning",
                    "docker",
                    "domain",
                    "domains",
                    "edge ai",
                    "embedded inference",
                    "framework",
                    "frameworks",
                    "ganomaly",
                    "halcon",
                    "industrial computer vision",
                    "java",
                    "knowledge distillation",
                    "language",
                    "languages",
                    "linux",
                    "machine learning",
                    "mlflow",
                    "numpy",
                    "opencv",
                    "openvino",
                    "onnx",
                    "pandas",
                    "patchcore",
                    "pytorch",
                    "production machine learning",
                    "real time computer vision",
                    "resnet",
                    "scikit learn",
                    "segmentation",
                    "specialization",
                    "specializations",
                    "sql",
                    "tensorboard",
                    "tensorrt",
                    "technical skills",
                    "technology",
                    "technologies",
                    "tool",
                    "tools",
                    "tensorflow",
                    "vae",
                    "vit",
                    "visual inspection",
                    "yolo",
                    "python",
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
                    "authored",
                    "preprint",
                    "preprints",
                    "pre-print",
                    "pre-prints",
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
                "preprint",
                "preprints",
                "pre-print",
                "pre-prints",
                "publication",
                "publications",
                "research",
                "submitted",
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
                    "codice",
                    "progetti",
                    "pubblicato",
                    "software di ricerca",
                )
            ),
        ),
        lexical_expansion_terms=frozenset(
            (
                "code",
                "github",
                "project",
                "projects",
                "public research software",
                "repositories",
                "repository",
                "research software",
                "software",
                "source",
                "source code",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "built",
                    "developed",
                    "repository",
                    "repositories",
                    "repo",
                    "repos",
                    "portfolio",
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
                    "come posso contattare",
                    "contattare",
                    "contattarlo",
                    "contatto",
                    "raggiungere",
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
                "public professional profile links",
                "website",
            )
        ),
        required_evidence_groups=(
            frozenset(
                (
                    "linkedin",
                    "website",
                    "orcid",
                    "portfolio",
                    "link",
                    "links",
                    "github",
                )
            ),
        ),
    ),
)

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

DEFAULT_INTENT_CATALOG = IntentCatalog(
    profiles=QUESTION_INTENT_PROFILES,
    contact_project_context_words=_PROJECT_CONTEXT_WORDS,
)


def detect_question_intents(question: str) -> tuple[QuestionIntent, ...]:
    """Return supported recruiter intents that match a question."""

    return DEFAULT_INTENT_CATALOG.detect_question_intents(question)


def profile_for_intent(intent: QuestionIntent) -> QuestionIntentProfile:
    """Return the immutable profile for one supported intent."""

    return DEFAULT_INTENT_CATALOG.profile_for_intent(intent)


def categories_for_intents(
    intents: tuple[QuestionIntent, ...],
) -> tuple[KnowledgeCategory, ...]:
    """Return accepted knowledge categories for detected intents in stable order."""

    return DEFAULT_INTENT_CATALOG.categories_for_intents(intents)


def text_satisfies_intent_evidence(text: str, intent: QuestionIntent) -> bool:
    """Return whether text contains the required evidence terms for an intent."""

    return DEFAULT_INTENT_CATALOG.text_satisfies_intent_evidence(text, intent)
