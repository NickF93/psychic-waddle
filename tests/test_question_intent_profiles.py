from __future__ import annotations

import pytest

from portfolio_rag_assistant.intent import (
    QUESTION_INTENT_PROFILES,
    categories_for_intents,
    detect_question_intents,
    profile_for_intent,
    text_satisfies_intent_evidence,
)


def test_profiles_define_unique_supported_recruiter_intents() -> None:
    intents = tuple(profile.intent for profile in QUESTION_INTENT_PROFILES)

    assert intents == (
        "workplace",
        "current_role",
        "skills",
        "education",
        "publications",
        "projects",
        "contact",
    )
    assert len(set(intents)) == len(intents)


@pytest.mark.parametrize(
    ("question", "expected_intents"),
    (
        ("Where did Niccolo work?", ("workplace",)),
        ("Who employs him now?", ("current_role",)),
        ("What is his current role?", ("current_role",)),
        ("What are his main ML skills?", ("skills",)),
        ("What publications does he have?", ("publications",)),
        ("Which GitHub repositories does he publish?", ("projects",)),
        ("Where can I find his LinkedIn?", ("contact",)),
    ),
)
def test_detect_question_intents_for_natural_recruiter_phrasings(
    question: str,
    expected_intents: tuple[str, ...],
) -> None:
    assert detect_question_intents(question) == expected_intents


@pytest.mark.parametrize(
    "question",
    (
        "What is his favorite pizza topping?",
        "What is his private phone number?",
        "What is his home address?",
        "What is his private email?",
        "Who won the football match yesterday?",
    ),
)
def test_detect_question_intents_rejects_unsupported_questions(
    question: str,
) -> None:
    assert detect_question_intents(question) == ()


def test_categories_for_intents_returns_stable_unique_categories() -> None:
    assert categories_for_intents(("workplace", "current_role")) == ("experience",)
    assert categories_for_intents(("publications", "projects", "contact")) == (
        "research",
        "projects",
        "contact",
    )


def test_profile_for_intent_exposes_retrieval_expansion_terms() -> None:
    workplace = profile_for_intent("workplace")

    assert workplace.accepted_categories == ("experience",)
    assert "work history" in workplace.lexical_expansion_terms
    assert "employers" in workplace.lexical_expansion_terms


@pytest.mark.parametrize(
    ("text", "intent"),
    (
        (
            "Niccolo Ferrari worked at NAIS S.r.l. in Bologna.",
            "workplace",
        ),
        (
            "Niccolo Ferrari's professional workplaces include NAIS S.r.l. "
            "and Bonfiglioli Engineering.",
            "workplace",
        ),
        (
            "Niccolo Ferrari's current role is Senior Machine Learning Engineer.",
            "current_role",
        ),
        (
            "Niccolo Ferrari currently works at NAIS S.r.l.",
            "current_role",
        ),
    ),
)
def test_text_satisfies_intent_evidence_uses_required_terms(
    text: str,
    intent: str,
) -> None:
    assert text_satisfies_intent_evidence(text, intent)


@pytest.mark.parametrize(
    ("text", "intent"),
    (
        (
            "Niccolo Ferrari worked on Ph.D. research in deep learning.",
            "workplace",
        ),
        (
            "Niccolo Ferrari has professional experience in computer vision.",
            "workplace",
        ),
        (
            "Niccolo Ferrari previously worked as a Machine Learning Engineer.",
            "current_role",
        ),
        (
            "Niccolo Ferrari has experience with role-based access control.",
            "current_role",
        ),
    ),
)
def test_text_satisfies_intent_evidence_rejects_incomplete_evidence(
    text: str,
    intent: str,
) -> None:
    assert not text_satisfies_intent_evidence(text, intent)
