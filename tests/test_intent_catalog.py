from __future__ import annotations

import json
from pathlib import Path

import pytest

from intent_catalog_helpers import TRACKED_INTENT_CATALOG
from portfolio_rag_assistant.intent import (
    QuestionIntent,
    QuestionIntentProfileError,
    load_intent_catalog,
)


def test_tracked_intent_catalog_loads_reviewed_profiles() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    assert tuple(profile.intent.identifier for profile in catalog.profiles) == (
        "professional_overview",
        "workplace",
        "current_role",
        "skills",
        "education",
        "publications",
        "projects",
        "contact",
    )


@pytest.mark.parametrize(
    "question",
    (
        "What is Niccolo's experience?",
        "Where did Niccolo work?",
        "Who employs him now?",
        "What are his main ML skills?",
        "Which GitHub repositories does he publish?",
        "Where can I find his LinkedIn?",
        "What is Niccolo favorite pizza topping?",
        "What is Niccolo's GitHub?",
        "What is Niccolo's GitHub profile?",
        "Where is his GitHub link?",
        "What GitHub repositories does Niccolo publish?",
        "Where is his source code?",
    ),
)
def test_tracked_intent_catalog_uses_positive_github_routing(question: str) -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    assert _intent_identifiers(catalog.detect_question_intents(question)) == (
        _expected_intents(question)
    )


def test_tracked_intent_catalog_reproduces_current_evidence_matching() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    for profile in catalog.profiles:
        assert catalog.profile_for_intent(profile.intent) == profile
        assert catalog.categories_for_intents((profile.intent,)) == (
            profile.accepted_categories
        )
        evidence_terms = tuple(
            sorted(group)[0] for group in profile.required_evidence_groups
        )
        text = f"evidence probe {' '.join(evidence_terms)}"
        assert catalog.text_satisfies_intent_evidence(text, profile.intent)


def test_tracked_intent_catalog_is_the_only_supported_intent_id_producer() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)
    workplace = catalog.intent_for_identifier("workplace")

    assert isinstance(workplace, QuestionIntent)
    assert workplace.identifier == "workplace"
    assert catalog.profile_for_intent(workplace).intent == workplace
    with pytest.raises(
        QuestionIntentProfileError,
        match="intent must be a catalog QuestionIntent",
    ):
        catalog.profile_for_intent("workplace")
    with pytest.raises(
        QuestionIntentProfileError,
        match="question intents must be created by an intent catalog",
    ):
        QuestionIntent("fabricated", _creation_token=object())


def test_load_intent_catalog_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["unexpected"] = True
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionIntentProfileError, match="unknown keys: unexpected"):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_retired_frozen_disambiguation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["frozen_disambiguation"] = {
        "contact_project_context_words": ["repository"]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        QuestionIntentProfileError,
        match="unknown keys: frozen_disambiguation",
    ):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_unknown_profile_keys(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["profiles"][0]["unexpected"] = True
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionIntentProfileError, match="unknown keys: unexpected"):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_duplicate_intents(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["profiles"][1]["intent"] = payload["profiles"][0]["intent"]
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        QuestionIntentProfileError,
        match="duplicate question intent profile",
    ):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_missing_catalog_file(tmp_path: Path) -> None:
    with pytest.raises(QuestionIntentProfileError, match="intent catalog file not found"):
        load_intent_catalog(tmp_path / "missing.json")


def _tracked_payload() -> dict:
    return json.loads(TRACKED_INTENT_CATALOG.read_text(encoding="utf-8"))


def _expected_intents(question: str) -> tuple[str, ...]:
    expected_by_question = {
        "What is Niccolo's experience?": ("professional_overview",),
        "Where did Niccolo work?": ("workplace",),
        "Who employs him now?": ("current_role",),
        "What are his main ML skills?": ("skills",),
        "Which GitHub repositories does he publish?": ("projects",),
        "Where can I find his LinkedIn?": ("contact",),
        "What is Niccolo favorite pizza topping?": (),
        "What is Niccolo's GitHub?": (),
        "What is Niccolo's GitHub profile?": ("contact",),
        "Where is his GitHub link?": ("contact",),
        "What GitHub repositories does Niccolo publish?": ("projects",),
        "Where is his source code?": ("projects",),
    }
    return expected_by_question[question]


def _intent_identifiers(intents: tuple[QuestionIntent, ...]) -> tuple[str, ...]:
    return tuple(intent.identifier for intent in intents)
