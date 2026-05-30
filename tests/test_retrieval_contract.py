from __future__ import annotations

import asyncio

import pytest

from portfolio_rag_assistant.retrieval import (
    RetrievedContext,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalScore,
    Retriever,
)


def test_fake_retriever_satisfies_contract() -> None:
    retriever = FakeRetriever(
        (
            RetrievedContext(
                chunk_id=1,
                chunk_text="experience: Niccolo worked at NAIS s.r.l.",
                category="experience",
                source_uri="cv://niccolo/main",
                source_title="Niccolo Ferrari CV",
                source_locator="Experience section",
                score=RetrievalScore(
                    combined_score=0.91,
                    vector_score=0.87,
                    keyword_score=1.0,
                ),
            ),
        )
    )

    response = _run(
        retriever.retrieve(
            RetrievalRequest(question="Where did Niccolo work?", top_k=3)
        )
    )

    assert isinstance(retriever, Retriever)
    assert response.question == "Where did Niccolo work?"
    assert response.results[0].source_uri == "cv://niccolo/main"
    assert response.results[0].score.combined_score == 0.91


def test_retrieval_request_requires_non_empty_question() -> None:
    with pytest.raises(ValueError, match="question"):
        RetrievalRequest(question=" ", top_k=3)


def test_retrieval_request_requires_positive_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        RetrievalRequest(question="Where did Niccolo work?", top_k=0)


def test_retrieval_score_rejects_negative_scores() -> None:
    with pytest.raises(ValueError, match="combined_score"):
        RetrievalScore(combined_score=-0.01)


def test_retrieved_context_requires_supported_category() -> None:
    with pytest.raises(ValueError, match="category"):
        RetrievedContext(
            chunk_id=1,
            chunk_text="misc: unsupported",
            category="misc",
            source_uri="cv://niccolo/main",
            source_title="Niccolo Ferrari CV",
            score=RetrievalScore(combined_score=0.4),
        )


def test_retrieved_context_enforces_public_visibility() -> None:
    with pytest.raises(ValueError, match="public_visible"):
        RetrievedContext(
            chunk_id=1,
            chunk_text="experience: private note",
            category="experience",
            source_uri="cv://niccolo/main",
            source_title="Niccolo Ferrari CV",
            score=RetrievalScore(combined_score=0.4),
            public_visible=False,
        )


def test_retrieval_response_requires_retrieved_context_results() -> None:
    with pytest.raises(ValueError, match="results"):
        RetrievalResponse(
            question="Where did Niccolo work?",
            results=("not a retrieved context",),
        )


def _run(awaitable):
    return asyncio.run(awaitable)


class FakeRetriever:
    def __init__(self, results: tuple[RetrievedContext, ...]) -> None:
        self._results = results
        self.requests: tuple[RetrievalRequest, ...] = ()

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.requests = (*self.requests, request)
        return RetrievalResponse(
            question=request.question,
            results=self._results[: request.top_k],
        )
