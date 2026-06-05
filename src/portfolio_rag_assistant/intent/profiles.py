"""Bounded recruiter-question intent profiles."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import InitVar, dataclass

from portfolio_rag_assistant.knowledge import (
    ALLOWED_KNOWLEDGE_CATEGORIES,
    KnowledgeCategory,
)


class QuestionIntentProfileError(Exception):
    """Raised when a question intent profile violates its bounded contract."""


_QUESTION_INTENT_TOKEN = object()


@dataclass(frozen=True, slots=True)
class QuestionIntent:
    """Catalog-owned identifier for one supported recruiter question intent."""

    identifier: str
    _creation_token: InitVar[object]

    def __post_init__(self, _creation_token: object) -> None:
        if _creation_token is not _QUESTION_INTENT_TOKEN:
            raise QuestionIntentProfileError(
                "question intents must be created by an intent catalog"
            )
        _require_non_empty_text(self.identifier, "intent")

    def __str__(self) -> str:
        return self.identifier


def _question_intent_from_catalog(identifier: str) -> QuestionIntent:
    return QuestionIntent(identifier, _creation_token=_QUESTION_INTENT_TOKEN)


@dataclass(frozen=True, slots=True)
class QuestionIntentProfile:
    """Deterministic vocabulary for one supported recruiter question intent."""

    intent: QuestionIntent
    accepted_categories: tuple[KnowledgeCategory, ...]
    trigger_groups: tuple[frozenset[str], ...]
    semantic_example_questions: tuple[str, ...]
    semantic_candidate_threshold: float
    semantic_required_threshold: float | None
    lexical_expansion_terms: frozenset[str]
    required_evidence_groups: tuple[frozenset[str], ...]

    def __post_init__(self) -> None:
        _require_question_intent(self.intent, "intent")
        _require_non_empty_tuple(self.accepted_categories, "accepted_categories")
        _require_non_empty_tuple(self.trigger_groups, "trigger_groups")
        _require_non_empty_text_tuple(
            self.semantic_example_questions,
            "semantic_example_questions",
        )
        _require_probability(
            self.semantic_candidate_threshold,
            "semantic_candidate_threshold",
        )
        if self.semantic_required_threshold is not None:
            _require_probability(
                self.semantic_required_threshold,
                "semantic_required_threshold",
            )
            if self.semantic_required_threshold < self.semantic_candidate_threshold:
                raise QuestionIntentProfileError(
                    "semantic_required_threshold must be at least "
                    "semantic_candidate_threshold"
                )
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
class SemanticCalibration:
    """Reviewed model-bound semantic intent calibration metadata."""

    embedding_backend: str
    embedding_model: str
    precision_floor: float
    minimum_required_support: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.embedding_backend, "embedding_backend")
        _require_non_empty_text(self.embedding_model, "embedding_model")
        _require_probability(self.precision_floor, "precision_floor")
        if not isinstance(self.minimum_required_support, int) or isinstance(
            self.minimum_required_support,
            bool,
        ):
            raise QuestionIntentProfileError(
                "minimum_required_support must be a positive integer"
            )
        if self.minimum_required_support <= 0:
            raise QuestionIntentProfileError(
                "minimum_required_support must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class IntentResolution:
    """Intent authority output for one visitor question."""

    required_intents: tuple[QuestionIntent, ...] = ()
    candidate_intents: tuple[QuestionIntent, ...] = ()

    def __post_init__(self) -> None:
        _require_question_intent_tuple(self.required_intents, "required_intents")
        _require_question_intent_tuple(self.candidate_intents, "candidate_intents")
        _require_unique_intents(self.required_intents, "required_intents")
        _require_unique_intents(self.candidate_intents, "candidate_intents")
        required_ids = {intent.identifier for intent in self.required_intents}
        candidate_ids = {intent.identifier for intent in self.candidate_intents}
        if required_ids & candidate_ids:
            raise QuestionIntentProfileError(
                "candidate_intents must not duplicate required_intents"
            )

    @property
    def retrieval_intents(self) -> tuple[QuestionIntent, ...]:
        """Return required plus candidate intents in stable catalog order."""

        intents: list[QuestionIntent] = []
        for intent in (*self.required_intents, *self.candidate_intents):
            if intent not in intents:
                intents.append(intent)
        return tuple(intents)


@dataclass(frozen=True, slots=True)
class IntentCatalog:
    """Reviewed deterministic vocabulary for supported recruiter intents."""

    semantic_calibration: SemanticCalibration
    profiles: tuple[QuestionIntentProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.semantic_calibration, SemanticCalibration):
            raise QuestionIntentProfileError(
                "semantic_calibration must be SemanticCalibration"
            )
        _require_non_empty_tuple(self.profiles, "profiles")
        for profile in self.profiles:
            if not isinstance(profile, QuestionIntentProfile):
                raise QuestionIntentProfileError(
                    "profiles must contain only QuestionIntentProfile values"
                )
        seen_intents: set[str] = set()
        for profile in self.profiles:
            if profile.intent.identifier in seen_intents:
                raise QuestionIntentProfileError(
                    f"duplicate question intent profile: {profile.intent}"
                )
            seen_intents.add(profile.intent.identifier)

    def intent_for_identifier(self, identifier: str) -> QuestionIntent:
        """Return the catalog-owned intent identifier for a reviewed string ID."""

        _require_non_empty_text(identifier, "intent")
        for profile in self.profiles:
            if profile.intent.identifier == identifier:
                return profile.intent
        raise QuestionIntentProfileError(
            f"unsupported question intent: {identifier}"
        )

    def detect_question_intents(self, question: str) -> tuple[QuestionIntent, ...]:
        """Return supported recruiter intents that match a question."""

        _require_non_empty_text(question, "question")
        intents: list[QuestionIntent] = []
        for profile in self.profiles:
            if not _term_groups_match(question, profile.trigger_groups):
                continue
            intents.append(profile.intent)
        return tuple(intents)

    def resolve_lexical_intents(self, question: str) -> IntentResolution:
        """Return a required-only resolution from deterministic lexical matching."""

        return IntentResolution(required_intents=self.detect_question_intents(question))

    def profile_for_intent(self, intent: QuestionIntent) -> QuestionIntentProfile:
        """Return the immutable profile for one supported intent."""

        _require_question_intent(intent, "intent")
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


def _require_question_intent(value: object, field_name: str) -> None:
    if not isinstance(value, QuestionIntent):
        raise QuestionIntentProfileError(
            f"{field_name} must be a catalog QuestionIntent"
        )


def _require_question_intent_tuple(
    value: tuple[object, ...],
    field_name: str,
) -> None:
    if not isinstance(value, tuple):
        raise QuestionIntentProfileError(f"{field_name} must be a tuple")
    for item in value:
        _require_question_intent(item, field_name)


def _require_unique_intents(
    intents: tuple[QuestionIntent, ...],
    field_name: str,
) -> None:
    seen: set[str] = set()
    for intent in intents:
        if intent.identifier in seen:
            raise QuestionIntentProfileError(f"{field_name} must not contain duplicates")
        seen.add(intent.identifier)


def _require_non_empty_tuple(value: tuple[object, ...], field_name: str) -> None:
    if not isinstance(value, tuple) or not value:
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty tuple")


def _require_non_empty_text_tuple(value: tuple[str, ...], field_name: str) -> None:
    _require_non_empty_tuple(value, field_name)
    for item in value:
        _require_non_empty_text(item, field_name)


def _require_non_empty_terms(value: frozenset[str], field_name: str) -> None:
    if not isinstance(value, frozenset) or not value:
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty frozenset")
    for term in value:
        _require_non_empty_text(term, field_name)


def _require_probability(value: float, field_name: str) -> None:
    if not isinstance(value, float) or isinstance(value, bool):
        raise QuestionIntentProfileError(f"{field_name} must be a float")
    if not 0.0 <= value <= 1.0:
        raise QuestionIntentProfileError(f"{field_name} must be between 0 and 1")
