from __future__ import annotations

import asyncio

import pytest

from portfolio_rag_assistant.answer import (
    AnswerGenerationRequest,
    AnswerGenerationRequestError,
    AnswerGenerationResponse,
    AnswerGenerator,
    AnswerSourceReference,
)
from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NOT_ANSWERABLE,
    AnswerPolicyDecision,
)
from portfolio_rag_assistant.retrieval import RetrievedContext, RetrievalScore


def test_fake_answer_generator_satisfies_contract() -> None:
    generator = FakeAnswerGenerator("Niccolo worked at NAIS s.r.l.")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Where did Niccolo work?",
                decision=_answerable_decision(),
                language="en",
            )
        )
    )

    assert isinstance(generator, AnswerGenerator)
    assert response.status == ANSWERABLE
    assert response.answer_text == "Niccolo worked at NAIS s.r.l."
    assert response.sources == (
        AnswerSourceReference(
            source_title="Niccolo Ferrari CV",
            source_uri="cv://niccolo/main",
            source_locator="Experience section",
        ),
    )


def test_answer_generation_request_rejects_blank_question() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="question"):
        AnswerGenerationRequest(
            question=" ",
            decision=_answerable_decision(),
            language="en",
        )


def test_answer_generation_request_rejects_unsupported_language() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="language"):
        AnswerGenerationRequest(
            question="Where did Niccolo work?",
            decision=_answerable_decision(),
            language="fr",
        )


def test_answer_generation_request_requires_policy_decision() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="decision"):
        AnswerGenerationRequest(
            question="Where did Niccolo work?",
            decision="answerable",
            language="en",
        )


def test_answerable_response_requires_sources() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="source references"):
        AnswerGenerationResponse(
            answer_text="Niccolo worked at NAIS s.r.l.",
            status=ANSWERABLE,
        )


def test_non_answerable_response_rejects_sources() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="source references"):
        AnswerGenerationResponse(
            answer_text="I do not have verified context for that.",
            status=NOT_ANSWERABLE,
            sources=(
                AnswerSourceReference(
                    source_title="Niccolo Ferrari CV",
                    source_uri="cv://niccolo/main",
                ),
            ),
        )


def test_source_reference_requires_source_identity() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="source_title"):
        AnswerSourceReference(source_title=" ", source_uri="cv://niccolo/main")


def test_answer_generation_response_requires_source_reference_items() -> None:
    with pytest.raises(AnswerGenerationRequestError, match="sources"):
        AnswerGenerationResponse(
            answer_text="Niccolo worked at NAIS s.r.l.",
            status=ANSWERABLE,
            sources=("not a source",),
        )


def _run(awaitable):
    return asyncio.run(awaitable)


def _answerable_decision() -> AnswerPolicyDecision:
    return AnswerPolicyDecision(
        status=ANSWERABLE,
        reason="sufficient_source_backed_context",
        approved_context=(_context(),),
    )


def _context() -> RetrievedContext:
    return RetrievedContext(
        chunk_id=1,
        chunk_text="experience: Niccolo worked at NAIS s.r.l.",
        category="experience",
        source_uri="cv://niccolo/main",
        source_title="Niccolo Ferrari CV",
        source_locator="Experience section",
        score=RetrievalScore(combined_score=0.91),
    )


class FakeAnswerGenerator:
    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text
        self.requests: tuple[AnswerGenerationRequest, ...] = ()

    async def generate(
        self,
        request: AnswerGenerationRequest,
    ) -> AnswerGenerationResponse:
        self.requests = (*self.requests, request)
        sources = tuple(
            AnswerSourceReference(
                source_title=context.source_title,
                source_uri=context.source_uri,
                source_locator=context.source_locator,
            )
            for context in request.decision.approved_context
        )
        return AnswerGenerationResponse(
            answer_text=self.answer_text,
            status=request.decision.status,
            sources=sources,
        )
