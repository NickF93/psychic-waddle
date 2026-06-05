from __future__ import annotations

import json
from pathlib import Path

import pytest

from portfolio_rag_assistant.intent import (
    DEFAULT_INTENT_CATALOG,
    QUESTION_INTENT_PROFILES,
    QuestionIntentProfileError,
    load_intent_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
TRACKED_INTENT_CATALOG = ROOT / "config" / "intent-profiles.json"


def test_tracked_intent_catalog_reproduces_current_literal_profiles() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    assert catalog.profiles == QUESTION_INTENT_PROFILES
    assert catalog.contact_project_context_words == (
        DEFAULT_INTENT_CATALOG.contact_project_context_words
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
        "What GitHub repositories does Niccolo publish?",
    ),
)
def test_tracked_intent_catalog_reproduces_current_detection(question: str) -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    assert catalog.detect_question_intents(question) == (
        DEFAULT_INTENT_CATALOG.detect_question_intents(question)
    )


def test_tracked_intent_catalog_reproduces_current_evidence_matching() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    for profile in DEFAULT_INTENT_CATALOG.profiles:
        assert catalog.profile_for_intent(profile.intent) == profile
        assert catalog.categories_for_intents((profile.intent,)) == (
            DEFAULT_INTENT_CATALOG.categories_for_intents((profile.intent,))
        )
        for group in profile.required_evidence_groups:
            for term in group:
                text = f"evidence probe {term}"
                assert catalog.text_satisfies_intent_evidence(text, profile.intent) == (
                    DEFAULT_INTENT_CATALOG.text_satisfies_intent_evidence(
                        text,
                        profile.intent,
                    )
                )


def test_load_intent_catalog_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["unexpected"] = True
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionIntentProfileError, match="unknown keys: unexpected"):
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
