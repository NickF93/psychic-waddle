from __future__ import annotations

import json
from pathlib import Path

import pytest

from intent_catalog_helpers import TRACKED_INTENT_CATALOG
from portfolio_rag_assistant.intent import (
    IntentResolution,
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
        "license",
        "interests",
        "education",
        "publications",
        "projects",
        "contact",
    )
    assert all(profile.semantic_example_questions for profile in catalog.profiles)
    assert catalog.semantic_calibration.embedding_backend == "ollama"
    assert catalog.semantic_calibration.embedding_model == "nomic-embed-text"
    assert catalog.semantic_calibration.precision_floor == 1.0
    assert catalog.semantic_calibration.minimum_required_support == 2
    assert all(
        profile.semantic_candidate_threshold == 0.75
        for profile in catalog.profiles
    )
    assert all(
        profile.semantic_required_threshold is None
        for profile in catalog.profiles
    )


@pytest.mark.parametrize(
    "question",
    (
        "What is Niccolo's experience?",
        "Where did Niccolo work?",
        "Who employs him now?",
        "What are his main ML skills?",
        "Does Niccolo have a driving license?",
        "What are Niccolo's public interests?",
        "Which GitHub repositories does he publish?",
        "Where can I find his LinkedIn?",
        "What is Niccolo favorite pizza topping?",
        "What is Niccolo's GitHub?",
        "What is Niccolo's GitHub profile?",
        "Where is his GitHub link?",
        "What GitHub repositories does Niccolo publish?",
        "Where is his source code?",
        "What is Niccolo's source?",
        "Where is Niccolo's source?",
        "Can I see Niccolo's source?",
        "Does Niccolo have a source?",
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


@pytest.mark.parametrize(
    "question",
    (
        "What professional story should I know about Niccolo?",
        "Which organizations has Niccolo been part of?",
        "Which position does Niccolo hold at the moment?",
        "What technical strengths would Niccolo bring to a team?",
        "What academic credentials does Niccolo have?",
        "Has Niccolo contributed scholarly articles?",
        "Which implementations can I inspect from Niccolo?",
        "Where can a recruiter find Niccolo online?",
    ),
)
def test_semantic_examples_do_not_change_lexical_detection(question: str) -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    assert catalog.detect_question_intents(question) == ()


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


def test_tracked_intent_catalog_resolves_lexical_required_intents() -> None:
    catalog = load_intent_catalog(TRACKED_INTENT_CATALOG)

    resolution = catalog.resolve_lexical_intents("Where did Niccolo work?")

    assert isinstance(resolution, IntentResolution)
    assert _intent_identifiers(resolution.required_intents) == ("workplace",)
    assert resolution.candidate_intents == ()
    assert _intent_identifiers(resolution.retrieval_intents) == ("workplace",)


def test_load_intent_catalog_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["unexpected"] = True
    _write_payload(catalog_path, payload)

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
    _write_payload(catalog_path, payload)

    with pytest.raises(
        QuestionIntentProfileError,
        match="unknown keys: frozen_disambiguation",
    ):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_unknown_profile_keys(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["profiles"][0]["unexpected"] = True
    _write_payload(catalog_path, payload)

    with pytest.raises(QuestionIntentProfileError, match="unknown keys: unexpected"):
        load_intent_catalog(catalog_path)


@pytest.mark.parametrize(
    ("mutate_payload", "error"),
    (
        (
            lambda payload: payload.pop("profiles"),
            "missing keys: profiles",
        ),
        (
            lambda payload: payload.__setitem__("profiles", "not an array"),
            "profiles must be an array",
        ),
        (
            lambda payload: payload.__setitem__("profiles", []),
            "profiles must not be empty",
        ),
        (
            lambda payload: payload.__setitem__("schema_version", 1),
            "schema_version must be 4",
        ),
        (
            lambda payload: payload.pop("semantic_calibration"),
            "missing keys: semantic_calibration",
        ),
        (
            lambda payload: payload["semantic_calibration"].__setitem__(
                "unexpected",
                True,
            ),
            "semantic_calibration has unknown keys: unexpected",
        ),
        (
            lambda payload: payload["semantic_calibration"].__setitem__(
                "embedding_backend",
                "",
            ),
            "semantic_calibration.embedding_backend must be a non-empty string",
        ),
        (
            lambda payload: payload["semantic_calibration"].__setitem__(
                "precision_floor",
                1,
            ),
            "semantic_calibration.precision_floor must be a float",
        ),
        (
            lambda payload: payload["semantic_calibration"].__setitem__(
                "minimum_required_support",
                0,
            ),
            "semantic_calibration.minimum_required_support must be a positive integer",
        ),
        (
            lambda payload: payload["profiles"][0].pop("trigger_groups"),
            "missing keys: trigger_groups",
        ),
        (
            lambda payload: payload["profiles"].__setitem__(0, "not an object"),
            "profiles\\[0\\] must be an object",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "accepted_categories",
                "experience",
            ),
            "accepted_categories must be an array",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "accepted_categories",
                ["invalid-category"],
            ),
            "accepted_categories must contain only",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "trigger_groups",
                [[]],
            ),
            "trigger_groups\\[0\\] must not be empty",
        ),
        (
            lambda payload: payload["profiles"][0]["trigger_groups"].__setitem__(
                0,
                [""],
            ),
            "trigger_groups\\[0\\]\\[0\\] must be a non-empty string",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_example_questions",
                "not an array",
            ),
            "semantic_example_questions must be an array",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_example_questions",
                [],
            ),
            "semantic_example_questions must not be empty",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_example_questions",
                [""],
            ),
            "semantic_example_questions\\[0\\] must be a non-empty string",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_candidate_threshold",
                1,
            ),
            "semantic_candidate_threshold must be a float",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_candidate_threshold",
                1.1,
            ),
            "semantic_candidate_threshold must be between 0 and 1",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "semantic_required_threshold",
                0.7,
            ),
            "semantic_required_threshold must be at least "
            "semantic_candidate_threshold",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "lexical_expansion_terms",
                [],
            ),
            "lexical_expansion_terms must not be empty",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "required_evidence_groups",
                [],
            ),
            "required_evidence_groups must not be empty",
        ),
    ),
)
def test_load_intent_catalog_rejects_malformed_catalog_data(
    tmp_path: Path,
    mutate_payload,
    error: str,
) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    mutate_payload(payload)
    _write_payload(catalog_path, payload)

    with pytest.raises(QuestionIntentProfileError, match=error):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_duplicate_intents(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    payload = _tracked_payload()
    payload["profiles"][1]["intent"] = payload["profiles"][0]["intent"]
    _write_payload(catalog_path, payload)

    with pytest.raises(
        QuestionIntentProfileError,
        match="duplicate question intent profile",
    ):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_missing_catalog_file(tmp_path: Path) -> None:
    with pytest.raises(QuestionIntentProfileError, match="intent catalog file not found"):
        load_intent_catalog(tmp_path / "missing.json")


def test_load_intent_catalog_rejects_invalid_json(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    catalog_path.write_text("{", encoding="utf-8")

    with pytest.raises(QuestionIntentProfileError, match="must be valid JSON"):
        load_intent_catalog(catalog_path)


def test_load_intent_catalog_rejects_non_object_catalog(tmp_path: Path) -> None:
    catalog_path = tmp_path / "intent-profiles.json"
    catalog_path.write_text("[]", encoding="utf-8")

    with pytest.raises(QuestionIntentProfileError, match="must be an object"):
        load_intent_catalog(catalog_path)


def _tracked_payload() -> dict:
    return json.loads(TRACKED_INTENT_CATALOG.read_text(encoding="utf-8"))


def _write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _expected_intents(question: str) -> tuple[str, ...]:
    expected_by_question = {
        "What is Niccolo's experience?": ("professional_overview",),
        "Where did Niccolo work?": ("workplace",),
        "Who employs him now?": ("current_role",),
        "What are his main ML skills?": ("skills",),
        "Does Niccolo have a driving license?": ("license",),
        "Does Niccolo have a car license?": ("license",),
        "What are Niccolo's public interests?": ("interests",),
        "Which GitHub repositories does he publish?": ("projects",),
        "Where can I find his LinkedIn?": ("contact",),
        "What is Niccolo favorite pizza topping?": (),
        "What is Niccolo's GitHub?": (),
        "What is Niccolo's GitHub profile?": ("contact",),
        "Where is his GitHub link?": ("contact",),
        "What GitHub repositories does Niccolo publish?": ("projects",),
        "Where is his source code?": ("projects",),
        "What is Niccolo's source?": (),
        "Where is Niccolo's source?": (),
        "Can I see Niccolo's source?": (),
        "Does Niccolo have a source?": (),
    }
    return expected_by_question[question]


def _intent_identifiers(intents: tuple[QuestionIntent, ...]) -> tuple[str, ...]:
    return tuple(intent.identifier for intent in intents)
