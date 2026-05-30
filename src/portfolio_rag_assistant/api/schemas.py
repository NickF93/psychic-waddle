"""Public API schemas."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from portfolio_rag_assistant.answer import AnswerLanguage
from portfolio_rag_assistant.policy import ANSWERABLE, AnswerDecisionStatus

MAX_QUESTION_LENGTH = 1000
MAX_REQUEST_BODY_BYTES = 4096


class HealthResponseBody(BaseModel):
    """Public health response body."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"


class ErrorBody(BaseModel):
    """Stable public error response body."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ChatSourceBody(BaseModel):
    """Public source metadata safe for frontend display."""

    model_config = ConfigDict(extra="forbid")

    title: str
    locator: str | None = None

    @field_validator("title", "locator")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("source text must not be blank")
        return stripped


class ChatRequestBody(BaseModel):
    """Public chat request body."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(max_length=MAX_QUESTION_LENGTH)
    language: AnswerLanguage

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class ChatResponseBody(BaseModel):
    """Public chat response body."""

    model_config = ConfigDict(extra="forbid")

    status: AnswerDecisionStatus
    answer: str
    sources: tuple[ChatSourceBody, ...] = ()

    @field_validator("answer")
    @classmethod
    def _strip_answer(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("answer must not be blank")
        return stripped

    @model_validator(mode="after")
    def _validate_source_visibility(self) -> Self:
        if self.status == ANSWERABLE and not self.sources:
            raise ValueError("answerable responses require sources")
        if self.status != ANSWERABLE and self.sources:
            raise ValueError("non-answerable responses must not include sources")
        return self
