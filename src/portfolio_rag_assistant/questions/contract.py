"""Question collection contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class QuestionCollectionError(Exception):
    """Base error for question collection failures."""


class QuestionCollectionRequestError(QuestionCollectionError):
    """Raised when a question collection request is invalid."""


class QuestionCollectionStoreError(QuestionCollectionError):
    """Raised when a question event cannot be persisted."""


@dataclass(frozen=True, slots=True)
class QuestionCollectionRequest:
    """Raw unanswered question text approved for collection."""

    raw_question_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_question_text, str):
            raise QuestionCollectionRequestError(
                "raw_question_text must be a non-empty string"
            )
        raw_question_text = self.raw_question_text.strip()
        if not raw_question_text:
            raise QuestionCollectionRequestError(
                "raw_question_text must be a non-empty string"
            )
        object.__setattr__(self, "raw_question_text", raw_question_text)


@dataclass(frozen=True, slots=True)
class QuestionCollectionResult:
    """Question collection outcome."""

    recorded: bool
    event_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.recorded, bool):
            raise QuestionCollectionRequestError("recorded must be a boolean")
        if self.recorded:
            if (
                not isinstance(self.event_id, int)
                or isinstance(self.event_id, bool)
                or self.event_id <= 0
            ):
                raise QuestionCollectionRequestError(
                    "recorded results require a positive event_id"
                )
        elif self.event_id is not None:
            raise QuestionCollectionRequestError(
                "unrecorded results must not include event_id"
            )


@runtime_checkable
class QuestionCollector(Protocol):
    """Anonymous question improvement signal collector."""

    async def collect(
        self,
        request: QuestionCollectionRequest,
    ) -> QuestionCollectionResult:
        """Persist or intentionally ignore one unanswered question."""
