from __future__ import annotations

import pytest

from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NEEDS_CLARIFICATION,
    NOT_ANSWERABLE,
    AnswerPolicy,
    AnswerPolicyDecision,
    AnswerPolicyRequest,
    AnswerPolicyRequestError,
    DeterministicAnswerPolicy,
)
from portfolio_rag_assistant.retrieval import RetrievedContext, RetrievalScore


def test_policy_allows_relevant_source_backed_context() -> None:
    policy = DeterministicAnswerPolicy()

    decision = policy.decide(
        AnswerPolicyRequest(
            question="Where did Niccolò work?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text="experience: Niccolo worked at NAIS s.r.l.",
                    source_uri="cv://niccolo/main",
                    combined_score=0.91,
                ),
            ),
            min_score=0.7,
        )
    )

    assert isinstance(policy, AnswerPolicy)
    assert decision.status == ANSWERABLE
    assert decision.reason == "sufficient_source_backed_context"
    assert decision.approved_context[0].source_uri == "cv://niccolo/main"


def test_policy_rejects_empty_retrieval_results() -> None:
    decision = DeterministicAnswerPolicy().decide(
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "no_retrieved_context"
    assert decision.approved_context == ()


def test_policy_rejects_low_confidence_context() -> None:
    decision = DeterministicAnswerPolicy().decide(
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    combined_score=0.61,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "low_confidence_context"


def test_policy_rejects_unsupported_question_category() -> None:
    decision = DeterministicAnswerPolicy().decide(
        AnswerPolicyRequest(
            question="What degree does Niccolo have?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    combined_score=0.88,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"


def test_policy_asks_for_clarification_on_broad_multi_category_question() -> None:
    decision = DeterministicAnswerPolicy().decide(
        AnswerPolicyRequest(
            question="Tell me about Niccolo",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    combined_score=0.91,
                ),
                _context(
                    chunk_id=2,
                    category="projects",
                    chunk_text="projects: Niccolo built a portfolio assistant.",
                    source_uri="portfolio://projects/assistant",
                    combined_score=0.89,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NEEDS_CLARIFICATION
    assert decision.reason == "ambiguous_question"
    assert decision.approved_context == ()


def test_policy_filters_approved_context_by_question_category() -> None:
    decision = DeterministicAnswerPolicy().decide(
        AnswerPolicyRequest(
            question="Which projects did Niccolo build?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    combined_score=0.91,
                ),
                _context(
                    chunk_id=2,
                    category="projects",
                    chunk_text="projects: Niccolo built a portfolio assistant.",
                    source_uri="portfolio://projects/assistant",
                    combined_score=0.89,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert tuple(context.category for context in decision.approved_context) == (
        "projects",
    )


def test_answer_policy_request_validates_min_score() -> None:
    with pytest.raises(AnswerPolicyRequestError, match="min_score"):
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(),
            min_score=1.1,
        )


def test_answerable_decision_requires_approved_context() -> None:
    with pytest.raises(AnswerPolicyRequestError, match="approved_context"):
        AnswerPolicyDecision(
            status=ANSWERABLE,
            reason="sufficient_source_backed_context",
        )


def _context(
    *,
    chunk_id: int,
    category: str,
    combined_score: float,
    chunk_text: str = "experience: Niccolo worked at NAIS s.r.l.",
    source_uri: str = "cv://niccolo/main",
) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        chunk_text=chunk_text,
        category=category,
        source_uri=source_uri,
        source_title="Niccolo Ferrari CV",
        source_locator="Experience section",
        score=RetrievalScore(combined_score=combined_score),
    )
