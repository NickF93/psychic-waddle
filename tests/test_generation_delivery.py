import asyncio
from contextlib import aclosing

import pytest

from portfolio_rag_assistant.answer import (
    AnswerGenerationRequest,
    GroundedAnswerGenerator,
    AnswerGenerationProviderError,
)
from portfolio_rag_assistant.answer.contract import (
    AnswerDelta,
    AnswerGenerationResponse,
)
from portfolio_rag_assistant.config import (
    load_fallback_chat_provider_settings,
    load_request_timeout,
)
from portfolio_rag_assistant.provider import (
    ChatResponse,
    ChatMessage,
    LLMProviderTransportError,
    LLMProviderConfigurationError,
)
from portfolio_rag_assistant.config import RuntimeConfigurationError
from test_grounded_answer_generation import _answerable_decision

REQUEST = AnswerGenerationRequest(
    question="Where did Niccolo work?", decision=_answerable_decision(), language="en"
)


class Provider:
    def __init__(self, parts):
        self.parts = parts
        self.calls = 0
        self.closed = False
        self.models = []

    async def chat(self, request):
        self.calls += 1
        self.models.append(request.model)
        if isinstance(self.parts[0], Exception):
            raise self.parts[0]
        return ChatResponse(
            model=request.model,
            message=ChatMessage(role="assistant", content="".join(self.parts)),
        )

    async def stream_chat(self, request):
        self.calls += 1
        self.models.append(request.model)
        try:
            for part in self.parts:
                if isinstance(part, Exception):
                    raise part
                if isinstance(part, float):
                    await asyncio.sleep(part)
                else:
                    yield part
        finally:
            self.closed = True


def events(primary, fallback=None, **kwargs):
    generator = GroundedAnswerGenerator(
        primary,
        "primary-model",
        fallback_provider=fallback,
        fallback_model="local-model" if fallback else None,
        **kwargs,
    )

    async def run():
        return [item async for item in generator.stream(REQUEST)]

    return asyncio.run(run())


def test_one_explicit_fallback_and_model_selection_before_visible_content(caplog):
    primary = Provider([LLMProviderTransportError("secret upstream body")])
    fallback = Provider(["A grounded ", "answer."])
    result = events(primary, fallback)
    assert primary.calls == fallback.calls == 1
    assert primary.models == ["primary-model"] and fallback.models == ["local-model"]
    assert result[-1].status == "answerable" and result[-1].sources
    assert "secret" not in caplog.text


def test_no_fallback_after_partial_text():
    primary = Provider(["partial answer", LLMProviderTransportError("broken")])
    fallback = Provider(["different answer"])
    with pytest.raises(AnswerGenerationProviderError):
        events(primary, fallback)
    assert fallback.calls == 0 and primary.closed


def test_timeout_before_text_falls_back_once():
    primary = Provider([1.0, "late"])
    fallback = Provider(["local answer"])
    assert events(primary, fallback, primary_timeout=0.01)[-1].status == "answerable"
    assert primary.closed and fallback.calls == 1


def test_leading_whitespace_does_not_disable_fallback():
    fallback = Provider(["local answer"])
    result = events(Provider(["\n\n", LLMProviderTransportError("broken")]), fallback)
    assert fallback.calls == 1
    assert [item.text for item in result if isinstance(item, AnswerDelta)] == [
        "local answer"
    ]


def test_active_stream_can_outlast_inactivity_budget():
    result = events(Provider([0.015, "one", 0.015, "two"]), primary_timeout=0.025)
    assert result[-1].status == "answerable"


def test_provider_timeout_cannot_cancel_consumer_between_events():
    async def run():
        generator = GroundedAnswerGenerator(
            Provider(["answer"]), "primary", primary_timeout=0.01
        )
        async with aclosing(generator.stream(REQUEST)) as stream:
            await anext(stream)
            assert isinstance(await anext(stream), AnswerDelta)
            await asyncio.sleep(0.03)
            assert isinstance(await anext(stream), AnswerGenerationResponse)

    asyncio.run(run())


def test_fallback_failure_is_terminal():
    primary = Provider([LLMProviderTransportError("first")])
    fallback = Provider([LLMProviderTransportError("second")])
    with pytest.raises(AnswerGenerationProviderError):
        events(primary, fallback)
    assert primary.calls == fallback.calls == 1


@pytest.mark.parametrize("cut", range(1, len("INSUFFICIENT_APPROVED_CONTEXT")))
def test_split_sentinel_never_becomes_provisional_text(cut):
    sentinel = "INSUFFICIENT_APPROVED_CONTEXT"
    fallback = Provider(["must not run"])
    result = events(Provider([sentinel[:cut], sentinel[cut:]]), fallback)
    assert not any(isinstance(item, AnswerDelta) for item in result)
    assert result[-1].status == "not_answerable" and not result[-1].sources
    assert fallback.calls == 0


def test_final_insufficiency_classification_remains_authoritative():
    result = events(Provider(["I cannot ", "answer from the approved context."]))
    assert isinstance(result[-1], AnswerGenerationResponse)
    assert (
        result[-1].status == "not_answerable"
        and "approved context" not in result[-1].answer_text
    )


def test_cancellation_closes_upstream_without_fallback():
    primary = Provider(["partial answer", 1.0])
    fallback = Provider(["wrong"])

    async def run():
        generator = GroundedAnswerGenerator(
            primary, "primary", fallback_provider=fallback, fallback_model="local"
        )
        stream = generator.stream(REQUEST)
        await anext(stream)
        await anext(stream)
        task = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await stream.aclose()

    asyncio.run(run())
    assert primary.closed and fallback.calls == 0


def test_json_path_uses_the_same_explicit_fallback():
    primary = Provider([LLMProviderTransportError("unavailable")])
    fallback = Provider(["Local answer."])
    response = asyncio.run(
        GroundedAnswerGenerator(
            primary, "primary", fallback_provider=fallback, fallback_model="local"
        ).generate(REQUEST)
    )
    assert response.status == "answerable" and primary.calls == fallback.calls == 1


def test_optional_fallback_is_explicit_and_partial_configuration_is_rejected():
    assert load_fallback_chat_provider_settings({}) is None
    with pytest.raises(LLMProviderConfigurationError):
        load_fallback_chat_provider_settings({"CHAT_FALLBACK_MODEL": "local"})
    settings = load_fallback_chat_provider_settings(
        {
            "CHAT_FALLBACK_BACKEND": "ollama",
            "CHAT_FALLBACK_BASE_URL": "http://ollama:11434/api",
            "CHAT_FALLBACK_MODEL": "local",
        }
    )
    assert settings.api_key is None and settings.timeout_seconds == 180


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
def test_request_deadline_must_be_finite_and_positive(value):
    with pytest.raises(RuntimeConfigurationError):
        load_request_timeout({"CHAT_REQUEST_TIMEOUT_SECONDS": value})
