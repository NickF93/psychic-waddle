from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from intent_catalog_helpers import TRACKED_INTENT_CATALOG
from portfolio_rag_assistant.intent import load_intent_catalog
from portfolio_rag_assistant.intent.profiles import _normalized_text

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_EVALUATION_FIXTURE = (
    ROOT / "tests" / "fixtures" / "intent-semantic-evaluation.json"
)


def test_semantic_evaluation_fixture_uses_known_schema() -> None:
    payload = _semantic_evaluation_payload()

    assert payload["schema_version"] == 1
    assert isinstance(payload["cases"], list)
    assert payload["cases"]
    for case in payload["cases"]:
        assert set(case) == {
            "question",
            "language",
            "expected_required_intents",
        }
        assert isinstance(case["question"], str)
        assert case["question"].strip()
        assert case["language"] in {"en", "it"}
        assert isinstance(case["expected_required_intents"], list)
        assert all(
            isinstance(intent, str) and intent.strip()
            for intent in case["expected_required_intents"]
        )


def test_semantic_evaluation_fixture_references_catalog_intents() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)
    supported_intents = {profile.intent.identifier for profile in catalog.profiles}
    referenced_intents = {
        intent
        for case in _semantic_evaluation_cases()
        for intent in _expected_required_intents(case)
    }

    assert referenced_intents <= supported_intents
    assert supported_intents <= referenced_intents


def test_semantic_evaluation_fixture_includes_negative_cases() -> None:
    negative_questions = tuple(
        case["question"]
        for case in _semantic_evaluation_cases()
        if not _expected_required_intents(case)
    )

    assert "What salary should I offer Niccolo?" in negative_questions
    assert "Where does Niccolo live privately?" in negative_questions
    assert "Who won the match last night?" in negative_questions


def test_semantic_evaluation_fixture_does_not_reuse_catalog_anchors() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)
    normalized_anchor_questions = {
        _normalized_text(question)
        for profile in catalog.profiles
        for question in profile.semantic_example_questions
    }
    normalized_eval_questions = {
        _normalized_text(case["question"]) for case in _semantic_evaluation_cases()
    }

    assert normalized_eval_questions.isdisjoint(normalized_anchor_questions)


def _semantic_evaluation_payload() -> dict[str, Any]:
    return json.loads(SEMANTIC_EVALUATION_FIXTURE.read_text(encoding="utf-8"))


def _semantic_evaluation_cases() -> tuple[dict[str, Any], ...]:
    cases = _semantic_evaluation_payload()["cases"]
    return tuple(case for case in cases if isinstance(case, dict))


def _expected_required_intents(case: dict[str, Any]) -> tuple[str, ...]:
    expected_intents = case["expected_required_intents"]
    return tuple(intent for intent in expected_intents if isinstance(intent, str))
