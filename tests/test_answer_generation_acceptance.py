from __future__ import annotations

import asyncio

from portfolio_rag_assistant.answer import (
    AnswerGenerationRequest,
    AnswerSourceReference,
    GroundedAnswerGenerator,
)
from portfolio_rag_assistant.policy import ANSWERABLE, AnswerPolicyDecision
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from portfolio_rag_assistant.retrieval import RetrievedContext, RetrievalScore


def test_work_history_answer_is_generated_from_approved_context_only() -> None:
    provider = AcceptanceProvider(
        "Niccolo worked at NAIS s.r.l. and Bonfiglioli."
    )
    generator = GroundedAnswerGenerator(provider, "chat-model")

    response = _run(
        generator.generate(
            AnswerGenerationRequest(
                question="Where did Niccolo work?",
                decision=AnswerPolicyDecision(
                    status=ANSWERABLE,
                    reason="sufficient_source_backed_context",
                    approved_context=(
                        _context(
                            chunk_id=1,
                            chunk_text="experience: Niccolo worked at NAIS s.r.l.",
                        ),
                        _context(
                            chunk_id=2,
                            chunk_text="experience: Niccolo worked at Bonfiglioli.",
                        ),
                    ),
                ),
                language="en",
            )
        )
    )

    assert response.status == ANSWERABLE
    assert response.answer_text == (
        "Niccolo worked at NAIS s.r.l. and Bonfiglioli.\n\n"
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

    prompt = provider.chat_requests[0].messages[1].content
    assert "experience: Niccolo worked at NAIS s.r.l." in prompt
    assert "experience: Niccolo worked at Bonfiglioli." in prompt
    assert "Approved context:" in prompt
    assert "DATABASE_URL" not in prompt
    assert "QuestionCollector" not in prompt


def _run(awaitable):
    return asyncio.run(awaitable)


def _context(*, chunk_id: int, chunk_text: str) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        chunk_text=chunk_text,
        category="experience",
        source_uri="cv://niccolo/main",
        source_title="Niccolo Ferrari CV",
        source_locator="Experience section",
        score=RetrievalScore(combined_score=0.92),
    )


class AcceptanceProvider:
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
