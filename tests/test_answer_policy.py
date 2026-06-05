from __future__ import annotations

import pytest

from intent_catalog_helpers import tracked_intent_catalog
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
    policy = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog())

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
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
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
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
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
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
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


def test_policy_rejects_category_match_without_intent_support() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo has professional experience in "
                        "industrial computer vision."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"
    assert decision.approved_context == ()


def test_policy_rejects_workplace_question_with_non_workplace_work_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo worked on Ph.D. research in "
                        "deep learning and computer vision."
                    ),
                    combined_score=0.98,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"
    assert decision.approved_context == ()


def test_policy_allows_workplace_question_with_work_history_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Which employers did Niccolo have?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo Ferrari's professional workplaces "
                        "include NAIS S.r.l., Bonfiglioli Engineering, the "
                        "University of Ferrara, and CIAS."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert decision.approved_context[0].chunk_id == 1


def test_policy_rejects_current_role_question_with_old_role_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's current role?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: From April 2018 to December 2024, "
                        "Niccolo Ferrari worked at Bonfiglioli Engineering "
                        "as a Machine Learning Engineer."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"


def test_policy_allows_current_role_question_with_current_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's current role?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo Ferrari's current role is Senior "
                        "Machine Learning Engineer and Researcher at NAIS S.r.l."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert decision.approved_context[0].chunk_id == 1


def test_policy_allows_professional_overview_with_matching_evidence() -> None:
    chunk_text = (
        "experience: Niccolo Ferrari is a Senior Machine Learning Engineer "
        "and Researcher with a Ph.D. research background."
    )

    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's experience?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=chunk_text,
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert decision.approved_context[0].chunk_text == chunk_text


def test_policy_rejects_professional_overview_with_category_only_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's experience?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo Ferrari has public profile "
                        "information."
                    ),
                    combined_score=0.99,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"
    assert decision.approved_context == ()


@pytest.mark.parametrize(
    ("question", "category", "chunk_text"),
    (
        (
            "What are Niccolo's main machine learning skills?",
            "skills",
            (
                "skills: Niccolo Ferrari's main technical skills combine "
                "industrial computer vision, anomaly detection, C++ inference, "
                "Python, PyTorch, TensorFlow, Halcon, OpenCV, and Linux."
            ),
        ),
        (
            "What is Niccolo's education?",
            "education",
            (
                "education: Niccolo Ferrari's education includes a Ph.D., "
                "a Master's degree, and a Bachelor's degree at the University "
                "of Ferrara."
            ),
        ),
        (
            "What publications does Niccolo have?",
            "research",
            (
                "research: Niccolo Ferrari's publications and research outputs "
                "include GRD-Net, Mahalanobis PatchCore, and Graph Memory "
                "Transformer."
            ),
        ),
        (
            "What research software does Niccolo publish?",
            "projects",
            (
                "projects: Niccolo Ferrari's public research software and "
                "repositories include GRD-Net, MH-PatchCore, and "
                "AgentOrchestrator."
            ),
        ),
        (
            "Where can I find Niccolo's public profile links?",
            "contact",
            (
                "contact: Niccolo Ferrari's public professional profile links "
                "include GitHub, LinkedIn, portfolio website, and ORCID."
            ),
        ),
    ),
)
def test_policy_allows_common_recruiter_intents_with_matching_evidence(
    question: str,
    category: str,
    chunk_text: str,
) -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question=question,
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category=category,
                    chunk_text=chunk_text,
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert decision.approved_context[0].chunk_text == chunk_text


@pytest.mark.parametrize(
    ("question", "category", "chunk_text"),
    (
        (
            "What are Niccolo's main machine learning skills?",
            "skills",
            "skills: Niccolo Ferrari has public profile information.",
        ),
        (
            "What is Niccolo's education?",
            "education",
            "education: Niccolo Ferrari has public profile information.",
        ),
        (
            "What publications does Niccolo have?",
            "research",
            "research: Niccolo Ferrari has public profile information.",
        ),
        (
            "What research software does Niccolo publish?",
            "projects",
            "projects: Niccolo Ferrari has public profile information.",
        ),
        (
            "Where can I find Niccolo's public profile links?",
            "contact",
            "contact: Niccolo Ferrari has public profile information.",
        ),
    ),
)
def test_policy_rejects_common_recruiter_intents_with_category_only_context(
    question: str,
    category: str,
    chunk_text: str,
) -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question=question,
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category=category,
                    chunk_text=chunk_text,
                    combined_score=0.99,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"
    assert decision.approved_context == ()


@pytest.mark.parametrize(
    "chunk_text",
    (
        "skills: Niccolo Ferrari uses public profile information.",
        "skills: Niccolo Ferrari's skills include public profile information.",
        "skills: Niccolo Ferrari's skills includes public profile information.",
    ),
)
def test_policy_rejects_skills_context_with_generic_evidence_verbs_only(
    chunk_text: str,
) -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What are Niccolo's main machine learning skills?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="skills",
                    chunk_text=chunk_text,
                    combined_score=0.99,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "insufficient_intent_support"
    assert decision.approved_context == ()


def test_policy_allows_fit_question_with_experience_and_skills_evidence() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Is Niccolo a good fit for industrial computer vision roles?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo Ferrari is a Senior Machine "
                        "Learning Engineer and Researcher with professional "
                        "experience in industrial computer vision."
                    ),
                    combined_score=0.99,
                ),
                _context(
                    chunk_id=2,
                    category="skills",
                    chunk_text=(
                        "skills: Niccolo Ferrari's main technical skills combine "
                        "industrial computer vision, anomaly detection, "
                        "segmentation, C++ inference, Python, PyTorch, "
                        "TensorFlow, Halcon, OpenCV, ONNX, OpenVINO, TensorRT, "
                        "and Docker."
                    ),
                    combined_score=0.98,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert tuple(context.category for context in decision.approved_context) == (
        "experience",
        "skills",
    )


@pytest.mark.parametrize(
    ("category", "chunk_text"),
    (
        (
            "experience",
            (
                "experience: Niccolo Ferrari is a Senior Machine Learning "
                "Engineer and Researcher with professional experience in "
                "industrial computer vision."
            ),
        ),
        (
            "skills",
            (
                "skills: Niccolo Ferrari's main technical skills combine "
                "industrial computer vision, anomaly detection, segmentation, "
                "C++ inference, Python, PyTorch, TensorFlow, Halcon, OpenCV, "
                "ONNX, OpenVINO, TensorRT, and Docker."
            ),
        ),
    ),
)
def test_policy_rejects_fit_question_without_both_required_domains(
    category: str,
    chunk_text: str,
) -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Is Niccolo a good fit for industrial computer vision roles?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category=category,
                    chunk_text=chunk_text,
                    combined_score=0.99,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"
    assert decision.approved_context == ()


def test_policy_treats_github_repository_question_as_project_intent() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Which GitHub repositories does Niccolo publish?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="projects",
                    chunk_text=(
                        "projects: The GRD-Net repository is "
                        "https://github.com/NickF93/GRD-Net."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == ANSWERABLE
    assert tuple(context.category for context in decision.approved_context) == (
        "projects",
    )


def test_policy_rejects_bare_ambiguous_github_question() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's GitHub?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="contact",
                    chunk_text=(
                        "contact: Niccolo Ferrari's public professional profile "
                        "links include GitHub, LinkedIn, portfolio website, and "
                        "ORCID."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"
    assert decision.approved_context == ()


def test_policy_rejects_private_email_question_even_with_contact_context() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What is Niccolo's private email?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="contact",
                    chunk_text=(
                        "contact: Niccolo Ferrari's public professional profile "
                        "links include GitHub, LinkedIn, portfolio website, and "
                        "ORCID."
                    ),
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"
    assert decision.approved_context == ()


@pytest.mark.parametrize(
    "question",
    (
        "What is Niccolo favorite pizza topping?",
        "What is Niccolo private phone number?",
        "What is Niccolo's salary?",
        "What is Niccolo's political opinion?",
        "Will Niccolo move to Berlin next year?",
        "Who won the football match yesterday?",
        "Generate pizza poetry.",
    ),
)
def test_policy_rejects_uncategorized_unsupported_questions(
    question: str,
) -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question=question,
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    combined_score=0.96,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"
    assert decision.approved_context == ()


def test_policy_asks_for_clarification_on_broad_multi_category_question() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
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


def test_policy_asks_for_clarification_on_generic_broad_question() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="Tell me about Niccolo",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text=(
                        "experience: Niccolo Ferrari is a Senior Machine "
                        "Learning Engineer and Researcher."
                    ),
                    combined_score=0.91,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NEEDS_CLARIFICATION
    assert decision.reason == "ambiguous_question"
    assert decision.approved_context == ()


def test_policy_rejects_category_keyword_question_without_supported_profile() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
        AnswerPolicyRequest(
            question="What jobs does Niccolo have?",
            retrieved_context=(
                _context(
                    chunk_id=1,
                    category="experience",
                    chunk_text="experience: Niccolo worked at NAIS S.r.l.",
                    combined_score=0.99,
                ),
            ),
            min_score=0.7,
        )
    )

    assert decision.status == NOT_ANSWERABLE
    assert decision.reason == "unsupported_question_category"
    assert decision.approved_context == ()


def test_policy_filters_approved_context_by_question_category() -> None:
    decision = DeterministicAnswerPolicy(intent_catalog=tracked_intent_catalog()).decide(
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
