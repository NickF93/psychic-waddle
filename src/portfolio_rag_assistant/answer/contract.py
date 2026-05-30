"""Grounded answer generation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    AnswerDecisionStatus,
    AnswerPolicyDecision,
)
from portfolio_rag_assistant.policy.contract import ANSWER_POLICY_STATUSES

AnswerLanguage = Literal["en", "it"]

ANSWER_LANGUAGES: frozenset[str] = frozenset(("en", "it"))


class AnswerGenerationError(Exception):
    """Base error for answer generation failures."""


class AnswerGenerationConfigurationError(AnswerGenerationError):
    """Raised when an answer generator is configured incorrectly."""


class AnswerGenerationRequestError(AnswerGenerationError):
    """Raised when answer generation input violates the contract."""


class AnswerGenerationProviderError(AnswerGenerationError):
    """Raised when model I/O fails during answer generation."""


@dataclass(frozen=True, slots=True)
class AnswerSourceReference:
    """Deterministic source metadata attached to an answer."""

    source_title: str
    source_uri: str
    source_locator: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.source_title, "source_title")
        _require_non_empty_text(self.source_uri, "source_uri")
        if self.source_locator is not None:
            _require_non_empty_text(self.source_locator, "source_locator")


@dataclass(frozen=True, slots=True)
class AnswerGenerationRequest:
    """Question, policy decision, and explicit response language."""

    question: str
    decision: AnswerPolicyDecision
    language: AnswerLanguage

    def __post_init__(self) -> None:
        _require_non_empty_text(self.question, "question")
        if not isinstance(self.decision, AnswerPolicyDecision):
            raise AnswerGenerationRequestError(
                "decision must be an AnswerPolicyDecision"
            )
        if self.language not in ANSWER_LANGUAGES:
            allowed = ", ".join(sorted(ANSWER_LANGUAGES))
            raise AnswerGenerationRequestError(f"language must be one of: {allowed}")


@dataclass(frozen=True, slots=True)
class AnswerGenerationResponse:
    """Final answer text and deterministic source references."""

    answer_text: str
    status: AnswerDecisionStatus
    sources: tuple[AnswerSourceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text(self.answer_text, "answer_text")
        if self.status not in ANSWER_POLICY_STATUSES:
            allowed = ", ".join(sorted(ANSWER_POLICY_STATUSES))
            raise AnswerGenerationRequestError(f"status must be one of: {allowed}")
        _require_tuple_of_type(self.sources, AnswerSourceReference, "sources")
        if self.status == ANSWERABLE and not self.sources:
            raise AnswerGenerationRequestError(
                "answerable responses require source references"
            )
        if self.status != ANSWERABLE and self.sources:
            raise AnswerGenerationRequestError(
                "non-answerable responses must not include source references"
            )


@runtime_checkable
class AnswerGenerator(Protocol):
    """Answer authority for final wording only."""

    async def generate(
        self,
        request: AnswerGenerationRequest,
    ) -> AnswerGenerationResponse:
        """Return a recruiter-facing answer from a policy decision."""


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AnswerGenerationRequestError(
            f"{field_name} must be a non-empty string"
        )


def _require_tuple_of_type(
    values: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise AnswerGenerationRequestError(f"{field_name} must be a tuple")
    if not all(isinstance(value, item_type) for value in values):
        raise AnswerGenerationRequestError(
            f"{field_name} must contain only {item_type.__name__}"
        )
