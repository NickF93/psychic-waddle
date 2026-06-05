from __future__ import annotations

import pytest

from intent_catalog_helpers import tracked_intent_catalog
from portfolio_rag_assistant.intent import IntentCatalog, QuestionIntent


def test_profiles_define_unique_supported_recruiter_intents() -> None:
    catalog = tracked_intent_catalog()
    intents = tuple(profile.intent.identifier for profile in catalog.profiles)

    assert intents == (
        "professional_overview",
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
        ("What is Niccolo's experience?", ("professional_overview",)),
        ("What is his professional background?", ("professional_overview",)),
        ("Can you summarize his career?", ("professional_overview",)),
        ("Where did Niccolo work?", ("workplace",)),
        ("Who employs him now?", ("current_role",)),
        ("What is his current role?", ("current_role",)),
        ("What are his main ML skills?", ("skills",)),
        ("What publications does he have?", ("publications",)),
        ("Which GitHub repositories does he publish?", ("projects",)),
        ("Where can I find his LinkedIn?", ("contact",)),
        ("Qual e il ruolo attuale di Niccolo?", ("current_role",)),
        ("Chi e il datore di lavoro attuale di Niccolo?", ("current_role",)),
        ("Come posso contattare Niccolo?", ("contact",)),
        ("What pre-prints does Niccolo have?", ("publications",)),
        ("What preprint does Niccolo have?", ("publications",)),
        ("Quali software di ricerca ha pubblicato Niccolo?", ("projects",)),
        ("What kind of work does Niccolo do?", ("professional_overview",)),
        ("What type of work does Niccolo do?", ("professional_overview",)),
        ("What is Niccolo specialized in?", ("skills",)),
        ("What does Niccolo do with anomaly detection?", ("skills",)),
        (
            "Is Niccolo a good fit for industrial computer vision roles?",
            ("professional_overview", "skills"),
        ),
        (
            "Would Niccolo be suitable for industrial computer vision roles?",
            ("professional_overview", "skills"),
        ),
        (
            "Is Niccolo the right person for industrial computer vision roles?",
            ("professional_overview", "skills"),
        ),
    ),
)
def test_detect_question_intents_for_natural_recruiter_phrasings(
    question: str,
    expected_intents: tuple[str, ...],
) -> None:
    actual_intents = tracked_intent_catalog().detect_question_intents(question)

    assert _intent_identifiers(actual_intents) == expected_intents


@pytest.mark.parametrize(
    "question",
    (
        "Tell me about Niccolo",
        "Describe Niccolo",
        "Give me an overview of his profile",
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
    assert tracked_intent_catalog().detect_question_intents(question) == ()


def test_categories_for_intents_returns_stable_unique_categories() -> None:
    catalog = tracked_intent_catalog()

    assert catalog.categories_for_intents(
        _intents(catalog, "professional_overview", "workplace", "current_role")
    ) == ("experience",)
    assert catalog.categories_for_intents(
        _intents(catalog, "publications", "projects", "contact")
    ) == (
        "research",
        "projects",
        "contact",
    )


def test_profile_for_intent_exposes_retrieval_expansion_terms() -> None:
    catalog = tracked_intent_catalog()
    workplace = catalog.profile_for_intent(catalog.intent_for_identifier("workplace"))

    assert workplace.accepted_categories == ("experience",)
    assert "professional workplaces" in workplace.lexical_expansion_terms
    assert "work history" in workplace.lexical_expansion_terms
    assert "employers" in workplace.lexical_expansion_terms
    assert "work" not in workplace.lexical_expansion_terms
    assert "worked" not in workplace.lexical_expansion_terms


@pytest.mark.parametrize(
    ("text", "intent"),
    (
        (
            "Niccolo Ferrari is a Senior Machine Learning Engineer and Researcher "
            "with a Ph.D. research background.",
            "professional_overview",
        ),
        (
            "Niccolo Ferrari's work history includes Senior Machine Learning "
            "Engineer at NAIS S.r.l. and Machine Learning Engineer at "
            "Bonfiglioli Engineering.",
            "professional_overview",
        ),
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
        (
            "Niccolo Ferrari uses Docker for reproducible machine learning "
            "environments.",
            "skills",
        ),
        (
            "Niccolo Ferrari's production deployment skills include C++, "
            "ONNX, OpenVINO, and TensorRT.",
            "skills",
        ),
        (
            "Niccolo Ferrari's computer vision architecture experience includes "
            "CNNs, ResNet, ViT, and YOLO models.",
            "skills",
        ),
        (
            "Niccolo Ferrari's areas of specialization include industrial "
            "computer vision and visual inspection.",
            "skills",
        ),
    ),
)
def test_text_satisfies_intent_evidence_uses_required_terms(
    text: str,
    intent: str,
) -> None:
    catalog = tracked_intent_catalog()

    assert catalog.text_satisfies_intent_evidence(
        text,
        catalog.intent_for_identifier(intent),
    )


@pytest.mark.parametrize(
    ("text", "intent"),
    (
        (
            "experience: Niccolo Ferrari has public profile information.",
            "professional_overview",
        ),
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
        (
            "skills: Niccolo Ferrari has public profile information.",
            "skills",
        ),
        (
            "skills: Niccolo Ferrari uses public profile information.",
            "skills",
        ),
        (
            "skills: Niccolo Ferrari's skills include public profile information.",
            "skills",
        ),
        (
            "skills: Niccolo Ferrari's skills includes public profile information.",
            "skills",
        ),
        (
            "education: Niccolo Ferrari has public profile information.",
            "education",
        ),
        (
            "research: Niccolo Ferrari has public profile information.",
            "publications",
        ),
        (
            "projects: Niccolo Ferrari has public profile information.",
            "projects",
        ),
        (
            "contact: Niccolo Ferrari has public profile information.",
            "contact",
        ),
    ),
)
def test_text_satisfies_intent_evidence_rejects_incomplete_evidence(
    text: str,
    intent: str,
) -> None:
    catalog = tracked_intent_catalog()

    assert not catalog.text_satisfies_intent_evidence(
        text,
        catalog.intent_for_identifier(intent),
    )


def _intent_identifiers(intents: tuple[QuestionIntent, ...]) -> tuple[str, ...]:
    return tuple(intent.identifier for intent in intents)


def _intents(
    catalog: IntentCatalog,
    *identifiers: str,
) -> tuple[QuestionIntent, ...]:
    return tuple(catalog.intent_for_identifier(identifier) for identifier in identifiers)
