from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from portfolio_rag_assistant.api import (
    MAX_QUESTION_LENGTH,
    ChatRequestBody,
    ChatResponseBody,
    ChatSourceBody,
)
from portfolio_rag_assistant.api.app import RequestSizeLimitMiddleware


def test_chat_request_accepts_explicit_english_and_italian() -> None:
    english = ChatRequestBody(
        question=" Where did Niccolo work? ",
        language="en",
    )
    italian = ChatRequestBody(
        question=" Dove ha lavorato Niccolo? ",
        language="it",
    )

    assert english.question == "Where did Niccolo work?"
    assert english.language == "en"
    assert italian.question == "Dove ha lavorato Niccolo?"
    assert italian.language == "it"


@pytest.mark.parametrize("question", ("", "   "))
def test_chat_request_rejects_blank_questions(question: str) -> None:
    with pytest.raises(ValidationError, match="question must not be blank"):
        ChatRequestBody(question=question, language="en")


def test_chat_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        ChatRequestBody(question="Where did Niccolo work?", language="fr")


def test_chat_request_rejects_oversized_question() -> None:
    with pytest.raises(ValidationError):
        ChatRequestBody(question="x" * (MAX_QUESTION_LENGTH + 1), language="en")


def test_chat_response_exposes_only_public_source_fields() -> None:
    response = ChatResponseBody(
        status="answerable",
        answer=" Niccolo worked at NAIS s.r.l. ",
        sources=(
            ChatSourceBody(
                title=" Niccolo Ferrari CV ",
                locator=" Experience section ",
            ),
        ),
    )

    assert response.model_dump(mode="json", exclude_none=True) == {
        "status": "answerable",
        "answer": "Niccolo worked at NAIS s.r.l.",
        "sources": [
            {
                "title": "Niccolo Ferrari CV",
                "locator": "Experience section",
            }
        ],
    }

    with pytest.raises(ValidationError):
        ChatSourceBody(
            title="Niccolo Ferrari CV",
            source_uri="cv://niccolo/main",
        )


def test_chat_response_sources_are_answerable_only() -> None:
    ChatResponseBody(
        status="not_answerable",
        answer="I do not have verified public context to answer that reliably.",
    )

    with pytest.raises(ValidationError, match="answerable responses require sources"):
        ChatResponseBody(status="answerable", answer="Answer", sources=())

    with pytest.raises(
        ValidationError,
        match="non-answerable responses must not include sources",
    ):
        ChatResponseBody(
            status="needs_clarification",
            answer="Please clarify.",
            sources=(ChatSourceBody(title="Niccolo Ferrari CV"),),
        )


def test_request_size_guard_rejects_oversized_body() -> None:
    accepted = _run_size_guard(body=b"1234", max_body_bytes=4)
    rejected = _run_size_guard(body=b"12345", max_body_bytes=4)

    assert accepted[0]["status"] == 200
    assert json.loads(accepted[1]["body"]) == {"ok": True}
    assert rejected[0]["status"] == 413
    assert json.loads(rejected[1]["body"]) == {
        "error": {
            "code": "request_too_large",
            "message": "request body is too large",
        }
    }


def _run_size_guard(
    *,
    body: bytes,
    max_body_bytes: int,
) -> list[dict[str, object]]:
    async def downstream_app(scope, receive, send) -> None:
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"ok":true}',
            }
        )

    async def run() -> list[dict[str, object]]:
        messages = [{"type": "http.request", "body": body, "more_body": False}]
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return messages.pop(0)

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [(b"content-length", str(len(body)).encode("ascii"))],
        }
        app = RequestSizeLimitMiddleware(
            downstream_app,
            max_body_bytes=max_body_bytes,
        )
        await app(scope, receive, send)
        return sent

    return asyncio.run(run())
