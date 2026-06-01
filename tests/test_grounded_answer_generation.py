from __future__ import annotations

import asyncio

import pytest

from portfolio_rag_assistant.answer import (
    AnswerGenerationConfigurationError,
    AnswerGenerationProviderError,
    AnswerGenerationRequest,
    AnswerSourceReference,
    GroundedAnswerGenerator,
)
from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NEEDS_CLARIFICATION,
    NOT_ANSWERABLE,
    AnswerPolicyDecision,
)
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProviderTransportError,
)
from portfolio_rag_assistant.retrieval import RetrievedContext, RetrievalScore


def test_grounded_generator_calls_chat_for_answerable_decision() -> None:
    provider = FakeProvider("Niccolo worked at NAIS s.r.l.")
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Where did Niccolo work?",
                decision=_answerable_decision(),
                language="en",
            )
        )
    )

    assert response.status == ANSWERABLE
    assert response.answer_text == (
        "Niccolo worked at NAIS s.r.l.\n\n"
        "Sources: Niccolo Ferrari CV (Experience section)."
    )
    assert response.sources == (
        AnswerSourceReference(
            source_title="Niccolo Ferrari CV",
            source_uri="cv://niccolo/main",
            source_locator="Experience section",
        ),
    )
    assert len(provider.chat_requests) == 1
    assert provider.embed_requests == ()


def test_grounded_generator_prompt_uses_only_approved_context() -> None:
    provider = FakeProvider("Niccolo worked at NAIS s.r.l.")
    generator = GroundedAnswerGenerator(provider, "chat-model")

    _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Where did Niccolo work?",
                decision=_answerable_decision(
                    chunk_text="experience: Niccolo worked at NAIS s.r.l."
                ),
                language="en",
            )
        )
    )

    user_prompt = provider.chat_requests[0].messages[1].content
    system_prompt = provider.chat_requests[0].messages[0].content
    assert "experience: Niccolo worked at NAIS s.r.l." in user_prompt
    assert "Bonfiglioli" not in user_prompt
    assert "combined_score" not in user_prompt
    assert "0.91" not in user_prompt
    assert "cv://niccolo/main" not in user_prompt
    assert "Do not add citations or source labels" in system_prompt
    assert "INSUFFICIENT_APPROVED_CONTEXT" in system_prompt
    assert "available verified context is not enough" not in system_prompt


@pytest.mark.parametrize(
    "provider_answer",
    (
        "INSUFFICIENT_APPROVED_CONTEXT",
        "The approved context is insufficient to answer that.",
        "The available verified context is not enough to determine that.",
        "Non ho contesto pubblico verificato per rispondere.",
    ),
)
def test_grounded_generator_demotes_insufficient_answerable_output(
    provider_answer: str,
) -> None:
    provider = FakeProvider(provider_answer)
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Where did Niccolo work?",
                decision=_answerable_decision(),
                language="en",
            )
        )
    )

    assert response.status == NOT_ANSWERABLE
    assert response.answer_text == (
        "I do not have verified public context to answer that reliably."
    )
    assert response.sources == ()
    assert len(provider.chat_requests) == 1


def test_not_answerable_decision_returns_fallback_without_provider_call() -> None:
    provider = FakeProvider("should not be used")
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="What is Niccolo's private phone number?",
                decision=AnswerPolicyDecision(
                    status=NOT_ANSWERABLE,
                    reason="unsupported_question_category",
                ),
                language="en",
            )
        )
    )

    assert response.status == NOT_ANSWERABLE
    assert response.answer_text == (
        "I do not have verified public context to answer that reliably."
    )
    assert response.sources == ()
    assert provider.chat_requests == ()
    assert provider.embed_requests == ()


def test_clarification_decision_returns_prompt_without_provider_call() -> None:
    provider = FakeProvider("should not be used")
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Tell me about Niccolo",
                decision=AnswerPolicyDecision(
                    status=NEEDS_CLARIFICATION,
                    reason="ambiguous_question",
                ),
                language="en",
            )
        )
    )

    assert response.status == NEEDS_CLARIFICATION
    assert "more specific question" in response.answer_text
    assert response.sources == ()
    assert provider.chat_requests == ()
    assert provider.embed_requests == ()


def test_grounded_generator_preserves_explicit_italian_language() -> None:
    provider = FakeProvider("Niccolo ha lavorato presso NAIS s.r.l.")
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Dove ha lavorato Niccolo?",
                decision=_answerable_decision(),
                language="it",
            )
        )
    )

    user_prompt = provider.chat_requests[0].messages[1].content
    assert "Requested language: Italian" in user_prompt
    assert response.answer_text == (
        "Niccolo ha lavorato presso NAIS s.r.l.\n\n"
        "Fonti: Niccolo Ferrari CV (Experience section)."
    )


def test_grounded_generator_wraps_provider_errors() -> None:
    provider = FailingProvider()
    generator = GroundedAnswerGenerator(provider, "chat-model")

    with pytest.raises(AnswerGenerationProviderError, match="provider chat failed"):
        _run(
            generator.generate(
                AnswerGenerationRequest(
                    question="Where did Niccolo work?",
                    decision=_answerable_decision(),
                    language="en",
                )
            )
        )


def test_grounded_generator_requires_chat_model() -> None:
    with pytest.raises(AnswerGenerationConfigurationError, match="chat_model"):
        GroundedAnswerGenerator(FakeProvider("answer"), " ")


def _run(awaitable):
    return asyncio.run(awaitable)


def _answerable_decision(
    *,
    chunk_text: str = "experience: Niccolo worked at NAIS s.r.l.",
) -> AnswerPolicyDecision:
    return AnswerPolicyDecision(
        status=ANSWERABLE,
        reason="sufficient_source_backed_context",
        approved_context=(
            RetrievedContext(
                chunk_id=1,
                chunk_text=chunk_text,
                category="experience",
                source_uri="cv://niccolo/main",
                source_title="Niccolo Ferrari CV",
                source_locator="Experience section",
                score=RetrievalScore(combined_score=0.91),
            ),
        ),
    )


class FakeProvider:
    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text
        self.chat_requests: tuple[ChatRequest, ...] = ()
        self.embed_requests: tuple[EmbeddingRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        return ChatResponse(
            model=request.model,
            message=ChatMessage(role="assistant", content=self.answer_text),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.embed_requests = (*self.embed_requests, request)
        return EmbeddingResponse(model=request.model, embeddings=((0.0,),))


class FailingProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__("unused")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_requests = (*self.chat_requests, request)
        raise LLMProviderTransportError("network failure")
