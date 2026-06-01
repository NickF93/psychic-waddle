from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from portfolio_rag_assistant.knowledge.validation import validate_knowledge_files


ROOT = Path(__file__).resolve().parents[1]
PROFILE_KNOWLEDGE = ROOT / "knowledge" / "profile.json"


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
    _assert_fact_contains(facts, "publications", "grd-net", "mahalanobis patchcore")
    _assert_fact_contains(facts, "public research software", "grd-net", "mh-patchcore")
    _assert_fact_contains(facts, "public professional profile links", "github")
    _assert_fact_contains(facts, "public linkedin profile", "linkedin.com")


def _fact_texts() -> tuple[str, ...]:
    data = json.loads(PROFILE_KNOWLEDGE.read_text(encoding="utf-8"))
    facts = data["facts"]
    assert isinstance(facts, list)
    return tuple(_fact_text(fact) for fact in facts)


def _fact_text(fact: Any) -> str:
    assert isinstance(fact, dict)
    text = fact["fact_text"]
    assert isinstance(text, str)
    return text.lower()


def _assert_fact_contains(
    facts: tuple[str, ...],
    *required_fragments: str,
) -> None:
    assert any(
        all(fragment.lower() in fact for fragment in required_fragments)
        for fact in facts
    ), required_fragments
