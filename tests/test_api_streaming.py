import asyncio
from contextlib import aclosing

import httpx
import pytest

from portfolio_rag_assistant.api import create_api_app, ChatRequestBody
from portfolio_rag_assistant.api.service import ChatServiceError
from portfolio_rag_assistant.answer import GroundedAnswerGenerator
from portfolio_rag_assistant.policy import AnswerPolicyDecision
from test_chat_service import (
    _service,
    _context,
    _retrieval_response,
    FakeRetriever,
    FakePolicy,
    FakeQuestionCollector,
)
from test_generation_delivery import Provider

BODY = {"question": "Where did Niccolo work?", "language": "en"}


def service(provider, status="answerable", collector=None):
    context = _context()
    return _service(
        retriever=FakeRetriever(
            _retrieval_response(question=BODY["question"], results=(context,)), []
        ),
        policy=FakePolicy(
            AnswerPolicyDecision(
                status=status,
                reason="test",
                approved_context=(context,) if status == "answerable" else (),
            ),
            [],
        ),
        generator=GroundedAnswerGenerator(provider, "test"),
        question_collector=collector,
    )


def request(chat_service):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_api_app(chat_service=chat_service)
            ),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/chat", headers={"Accept": "text/event-stream"}, json=BODY
            )

    return asyncio.run(run())


def test_same_post_route_negotiates_stream_and_completes_with_sources():
    response = request(service(Provider(["An ", "answer."])))
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert response.headers["x-accel-buffering"] == "no"
    text = response.text
    assert (
        text.index('"phase": "retrieving"')
        < text.index("event: delta")
        < text.index("event: complete")
    )
    assert text.count("event: complete") == 1 and "Niccolo Ferrari CV" in text
    assert "cv://" not in text and "combined_score" not in text


def test_stream_insufficiency_keeps_question_collection_semantics():
    collector = FakeQuestionCollector(recorded=True)
    provider = Provider(["must not run"])
    response = request(service(provider, status="not_answerable", collector=collector))
    assert "event: complete" in response.text and "event: delta" not in response.text
    assert "question_recorded" in response.text and provider.calls == 0
    assert len(collector.requests) == 1


def test_partial_failure_is_an_error_event_without_false_completion():
    from portfolio_rag_assistant.provider import LLMProviderTransportError

    response = request(
        service(
            Provider(["partial", LLMProviderTransportError("private upstream body")])
        )
    )
    assert "event: delta" in response.text and "event: error" in response.text
    assert "event: complete" not in response.text and "private" not in response.text


def test_global_deadline_bounds_stream_and_json():
    chat_service = service(Provider([1.0, "late"]))
    chat_service._request_timeout = 0.01
    response = request(chat_service)
    assert "event: error" in response.text and "event: complete" not in response.text

    class SlowRetriever:
        async def retrieve(self, request):
            await asyncio.sleep(1)

    chat_service._retriever = SlowRetriever()
    with pytest.raises(ChatServiceError):
        asyncio.run(chat_service.answer(ChatRequestBody(**BODY)))


@pytest.mark.parametrize("failure", [RuntimeError("private detail"), TimeoutError()])
def test_retrieval_failures_always_terminate_with_safe_error_event(failure):
    class FailedRetriever:
        async def retrieve(self, request):
            raise failure

    chat_service = service(Provider(["must not run"]))
    chat_service._retriever = FailedRetriever()
    response = request(chat_service)
    assert "event: error" in response.text
    assert (
        "event: complete" not in response.text and "private detail" not in response.text
    )


def test_request_deadline_does_not_cancel_paused_consumer():
    async def run():
        chat_service = service(Provider(["answer"]))
        chat_service._request_timeout = 0.01
        async with aclosing(
            chat_service.stream_answer(ChatRequestBody(**BODY))
        ) as stream:
            assert (await anext(stream))["event"] == "status"
            await asyncio.sleep(0.03)
            assert (await anext(stream))["event"] == "error"

    asyncio.run(run())
