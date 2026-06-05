"""Reviewed lexical intent catalog loading."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from portfolio_rag_assistant.intent.profiles import (
    IntentCatalog,
    QuestionIntentProfile,
    QuestionIntentProfileError,
    _question_intent_from_catalog,
)
from portfolio_rag_assistant.knowledge import KnowledgeCategory

_SCHEMA_VERSION = 2
_TOP_LEVEL_KEYS = frozenset(("schema_version", "profiles"))
_PROFILE_KEYS = frozenset(
    (
        "intent",
        "accepted_categories",
        "trigger_groups",
        "lexical_expansion_terms",
        "required_evidence_groups",
    )
)


def load_intent_catalog(path: str | Path) -> IntentCatalog:
    """Load a reviewed lexical intent catalog from an explicit JSON path."""

    catalog_path = _require_catalog_path(path)
    try:
        raw_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise QuestionIntentProfileError(
            f"intent catalog file not found: {catalog_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise QuestionIntentProfileError(
            f"intent catalog must be valid JSON: {catalog_path}"
        ) from error

    catalog = _require_mapping(raw_catalog, "intent catalog")
    _require_exact_keys(catalog, _TOP_LEVEL_KEYS, "intent catalog")
    schema_version = catalog["schema_version"]
    if schema_version != _SCHEMA_VERSION:
        raise QuestionIntentProfileError(
            f"intent catalog schema_version must be {_SCHEMA_VERSION}"
        )

    return IntentCatalog(profiles=_load_profiles(catalog["profiles"]))


def _require_catalog_path(path: str | Path) -> Path:
    if isinstance(path, Path):
        catalog_path = path
    elif isinstance(path, str) and path.strip():
        catalog_path = Path(path.strip())
    else:
        raise QuestionIntentProfileError("intent catalog path must be set")
    return catalog_path


def _load_profiles(value: object) -> tuple[QuestionIntentProfile, ...]:
    values = _require_sequence(value, "profiles")
    if not values:
        raise QuestionIntentProfileError("profiles must not be empty")
    profiles = tuple(_load_profile(item, index) for index, item in enumerate(values))
    seen_intents: set[str] = set()
    for profile in profiles:
        if profile.intent in seen_intents:
            raise QuestionIntentProfileError(
                f"duplicate question intent profile: {profile.intent}"
            )
        seen_intents.add(profile.intent)
    return profiles


def _load_profile(value: object, index: int) -> QuestionIntentProfile:
    profile = _require_mapping(value, f"profiles[{index}]")
    _require_exact_keys(profile, _PROFILE_KEYS, f"profiles[{index}]")
    return QuestionIntentProfile(
        intent=_question_intent_from_catalog(
            _require_text(profile["intent"], f"profiles[{index}].intent"),
        ),
        accepted_categories=tuple(
            cast(
                KnowledgeCategory,
                category,
            )
            for category in _require_string_list(
                profile["accepted_categories"],
                f"profiles[{index}].accepted_categories",
            )
        ),
        trigger_groups=_require_term_groups(
            profile["trigger_groups"],
            f"profiles[{index}].trigger_groups",
        ),
        lexical_expansion_terms=frozenset(
            _require_string_list(
                profile["lexical_expansion_terms"],
                f"profiles[{index}].lexical_expansion_terms",
            )
        ),
        required_evidence_groups=_require_term_groups(
            profile["required_evidence_groups"],
            f"profiles[{index}].required_evidence_groups",
        ),
    )


def _require_term_groups(value: object, field_name: str) -> tuple[frozenset[str], ...]:
    groups = _require_sequence(value, field_name)
    if not groups:
        raise QuestionIntentProfileError(f"{field_name} must not be empty")
    return tuple(
        frozenset(_require_string_list(group, f"{field_name}[{index}]"))
        for index, group in enumerate(groups)
    )


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise QuestionIntentProfileError(f"{field_name} must be an object")
    for key in value:
        if not isinstance(key, str):
            raise QuestionIntentProfileError(f"{field_name} keys must be strings")
    return cast(Mapping[str, object], value)


def _require_exact_keys(
    value: Mapping[str, object],
    expected_keys: frozenset[str],
    field_name: str,
) -> None:
    actual_keys = frozenset(value)
    extra_keys = actual_keys - expected_keys
    missing_keys = expected_keys - actual_keys
    if extra_keys:
        keys = ", ".join(sorted(extra_keys))
        raise QuestionIntentProfileError(f"{field_name} has unknown keys: {keys}")
    if missing_keys:
        keys = ", ".join(sorted(missing_keys))
        raise QuestionIntentProfileError(f"{field_name} is missing keys: {keys}")


def _require_sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise QuestionIntentProfileError(f"{field_name} must be an array")
    return cast(Sequence[object], value)


def _require_string_list(value: object, field_name: str) -> tuple[str, ...]:
    values = _require_sequence(value, field_name)
    if not values:
        raise QuestionIntentProfileError(f"{field_name} must not be empty")
    return tuple(
        _require_text(item, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    )


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuestionIntentProfileError(f"{field_name} must be a non-empty string")
    return value.strip()
