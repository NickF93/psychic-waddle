from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portfolio_rag_assistant.knowledge.validation import validate_knowledge_files
from intent_catalog_helpers import tracked_intent_catalog


ROOT = Path(__file__).resolve().parents[1]
PROFILE_KNOWLEDGE = ROOT / "knowledge" / "profile.json"
EXPECTED_SOURCE_URI = "cv://niccolo/main"


@dataclass(frozen=True, slots=True)
class AggregateExpectation:
    intent: str
    source_locator: str
    fragments: tuple[str, ...]


AGGREGATE_EXPECTATIONS: tuple[AggregateExpectation, ...] = (
    AggregateExpectation(
        intent="workplace",
        source_locator="Professional Experience",
        fragments=("professional workplaces", "nais", "bonfiglioli", "cias"),
    ),
    AggregateExpectation(
        intent="current_role",
        source_locator="Professional Experience",
        fragments=("current role", "nais", "technical lead"),
    ),
    AggregateExpectation(
        intent="skills",
        source_locator="Professional Skills",
        fragments=("main technical skills", "computer vision", "pytorch"),
    ),
    AggregateExpectation(
        intent="skills",
        source_locator="License",
        fragments=("driving license", "license b"),
    ),
    AggregateExpectation(
        intent="interests",
        source_locator="Interests",
        fragments=("interests include", "artificial intelligence", "climbing"),
    ),
    AggregateExpectation(
        intent="education",
        source_locator="Degrees",
        fragments=("education includes", "ph.d.", "university of ferrara"),
    ),
    AggregateExpectation(
        intent="publications",
        source_locator="Publications and Research Outputs",
        fragments=(
            "publications and research outputs",
            "grd-net",
            "mahalanobis patchcore",
        ),
    ),
    AggregateExpectation(
        intent="projects",
        source_locator="Research Software",
        fragments=("public research software", "grd-net", "mh-patchcore"),
    ),
    AggregateExpectation(
        intent="contact",
        source_locator="Public profile links",
        fragments=("public professional profile links", "github", "linkedin"),
    ),
)


def test_tracked_profile_knowledge_is_valid() -> None:
    report = validate_knowledge_files((PROFILE_KNOWLEDGE,))

    assert report.source_count == 1
    assert report.fact_count >= 100
    assert report.public_fact_count == report.fact_count
    assert report.chunk_count == report.public_fact_count


def test_tracked_profile_knowledge_excludes_private_contact_data() -> None:
    text = PROFILE_KNOWLEDGE.read_text(encoding="utf-8")

    assert not re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )
    for forbidden in (
        "+39",
        "tel:",
        "whatsapp",
        "phone number",
        "birthdate",
        "date of birth",
        "home address",
        "street address",
        "raw transcript",
        "visitor question",
        "recruiter-derived",
        "question_recorded",
    ):
        assert forbidden not in text.lower()


def test_tracked_profile_knowledge_covers_common_recruiter_intents() -> None:
    facts = _fact_texts()

    _assert_fact_contains(facts, "work history", "nais", "bonfiglioli", "cias")
    _assert_fact_contains(facts, "current role", "nais", "technical lead")
    _assert_fact_contains(facts, "ph.d.", "university of ferrara")
    _assert_fact_contains(facts, "main programming languages", "c++", "python")
    _assert_fact_contains(facts, "main frameworks", "pytorch", "tensorflow")
    _assert_fact_contains(facts, "machine learning skills", "anomaly detection")
    _assert_fact_contains(facts, "driving license", "license b")
    _assert_fact_contains(facts, "interests include", "artificial intelligence")
    _assert_fact_contains(facts, "publications", "grd-net", "mahalanobis patchcore")
    _assert_fact_contains(facts, "public research software", "grd-net", "mh-patchcore")
    _assert_fact_contains(facts, "public professional profile links", "github")
    _assert_fact_contains(facts, "public linkedin profile", "linkedin.com")


def test_tracked_profile_aggregates_satisfy_intent_profiles() -> None:
    facts = _facts()
    catalog = tracked_intent_catalog()

    for expectation in AGGREGATE_EXPECTATIONS:
        fact = _find_fact(facts, *expectation.fragments)
        intent = catalog.intent_for_identifier(expectation.intent)
        profile = catalog.profile_for_intent(intent)
        text = _fact_text(fact)

        assert fact["source_uri"] == EXPECTED_SOURCE_URI
        assert fact["source_locator"] == expectation.source_locator
        assert fact["category"] in profile.accepted_categories
        assert catalog.text_satisfies_intent_evidence(text, intent)


def test_tracked_profile_aggregates_are_not_question_specific_hacks() -> None:
    facts = _facts()

    for expectation in AGGREGATE_EXPECTATIONS:
        text = _fact_text(_find_fact(facts, *expectation.fragments))

        assert "where did niccolo work" not in text
        assert "favorite pizza" not in text
        assert "question:" not in text


def _fact_texts() -> tuple[str, ...]:
    return tuple(_fact_text(fact) for fact in _facts())


def _facts() -> tuple[dict[str, Any], ...]:
    data = json.loads(PROFILE_KNOWLEDGE.read_text(encoding="utf-8"))
    facts = data["facts"]
    assert isinstance(facts, list)
    for fact in facts:
        assert isinstance(fact, dict)
    return tuple(facts)


def _fact_text(fact: dict[str, Any]) -> str:
    text = fact["fact_text"]
    assert isinstance(text, str)
    return text.lower()


def _find_fact(
    facts: tuple[dict[str, Any], ...],
    *required_fragments: str,
) -> dict[str, Any]:
    for fact in facts:
        text = _fact_text(fact)
        if all(fragment.lower() in text for fragment in required_fragments):
            return fact
    raise AssertionError(required_fragments)


def _assert_fact_contains(
    facts: tuple[str, ...],
    *required_fragments: str,
) -> None:
    assert any(
        all(fragment.lower() in fact for fragment in required_fragments)
        for fact in facts
    ), required_fragments
