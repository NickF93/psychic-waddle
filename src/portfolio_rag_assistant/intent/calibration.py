"""Offline semantic intent threshold proposal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from portfolio_rag_assistant.intent.profiles import (
    IntentCatalog,
    QuestionIntent,
    _normalized_text,
)
from portfolio_rag_assistant.intent.semantic import SemanticIntentResolver
from portfolio_rag_assistant.provider import (
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingVector,
)

_EVALUATION_SCHEMA_VERSION = 1
_REPORT_SCHEMA_VERSION = 1
_EVALUATION_KEYS = frozenset(("schema_version", "cases"))
_CASE_KEYS = frozenset(("question", "language", "expected_required_intents"))
_TMP_ROOT = Path("/tmp").resolve()


class SemanticIntentCalibrationError(Exception):
    """Raised when semantic threshold proposal cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class SemanticEvaluationCase:
    """One labeled semantic intent calibration question."""

    question: str
    language: str
    expected_required_intents: tuple[QuestionIntent, ...]


@dataclass(frozen=True, slots=True)
class IntentThresholdProposal:
    """Offline threshold proposal for one intent."""

    intent: QuestionIntent
    semantic_candidate_threshold: float
    proposed_semantic_required_threshold: float | None
    positive_support: int
    false_positive_count: int
    calibration_precision: float | None

    def to_json(self) -> dict[str, object]:
        return {
            "intent": self.intent.identifier,
            "semantic_candidate_threshold": self.semantic_candidate_threshold,
            "proposed_semantic_required_threshold": (
                self.proposed_semantic_required_threshold
            ),
            "positive_support": self.positive_support,
            "false_positive_count": self.false_positive_count,
            "calibration_precision": self.calibration_precision,
        }


@dataclass(frozen=True, slots=True)
class SemanticThresholdProposalReport:
    """Offline semantic threshold proposals for human review."""

    embedding_backend: str
    embedding_model: str
    precision_floor: float
    minimum_required_support: int
    proposals: tuple[IntentThresholdProposal, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": _REPORT_SCHEMA_VERSION,
            "embedding_backend": self.embedding_backend,
            "embedding_model": self.embedding_model,
            "precision_floor": self.precision_floor,
            "minimum_required_support": self.minimum_required_support,
            "catalog_write": "manual_review_required",
            "proposals": tuple(proposal.to_json() for proposal in self.proposals),
        }


async def propose_semantic_thresholds(
    *,
    catalog: IntentCatalog,
    provider: EmbeddingProvider,
    embedding_model: str,
    evaluation_path: str | Path,
) -> SemanticThresholdProposalReport:
    """Produce reviewed-catalog threshold proposals without writing the catalog."""

    cases = load_semantic_evaluation_cases(
        path=evaluation_path,
        catalog=catalog,
    )
    evaluation_embeddings = await _embed_evaluation_questions(
        provider=provider,
        embedding_model=embedding_model,
        cases=cases,
    )
    resolver = SemanticIntentResolver(
        catalog=catalog,
        provider=provider,
        embedding_model=embedding_model,
    )
    score_rows: list[dict[str, float]] = []
    for embedding in evaluation_embeddings:
        score_rows.append(
            {
                score.intent.identifier: score.score
                for score in await resolver.score_semantic_intents(embedding)
            }
        )
    scores_by_case = tuple(score_rows)
    proposals = tuple(
        _propose_threshold_for_intent(
            catalog=catalog,
            intent=profile.intent,
            cases=cases,
            scores_by_case=scores_by_case,
        )
        for profile in catalog.profiles
    )
    return SemanticThresholdProposalReport(
        embedding_backend=catalog.semantic_calibration.embedding_backend,
        embedding_model=catalog.semantic_calibration.embedding_model,
        precision_floor=catalog.semantic_calibration.precision_floor,
        minimum_required_support=catalog.semantic_calibration.minimum_required_support,
        proposals=proposals,
    )


def load_semantic_evaluation_cases(
    *,
    path: str | Path,
    catalog: IntentCatalog,
) -> tuple[SemanticEvaluationCase, ...]:
    """Load labeled semantic calibration cases for a reviewed catalog."""

    evaluation_path = _require_path(path, "evaluation path")
    try:
        raw_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SemanticIntentCalibrationError(
            f"semantic evaluation fixture not found: {evaluation_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise SemanticIntentCalibrationError(
            f"semantic evaluation fixture must be valid JSON: {evaluation_path}"
        ) from error

    payload = _require_mapping(raw_payload, "semantic evaluation fixture")
    _require_exact_keys(payload, _EVALUATION_KEYS, "semantic evaluation fixture")
    if payload["schema_version"] != _EVALUATION_SCHEMA_VERSION:
        raise SemanticIntentCalibrationError(
            "semantic evaluation fixture schema_version must be "
            f"{_EVALUATION_SCHEMA_VERSION}"
        )
    raw_cases = _require_sequence(payload["cases"], "cases")
    if not raw_cases:
        raise SemanticIntentCalibrationError("cases must not be empty")
    return tuple(
        _load_case(case, index, catalog)
        for index, case in enumerate(raw_cases)
    )


def build_near_duplicate_review_report(
    *,
    catalog: IntentCatalog,
    cases: tuple[SemanticEvaluationCase, ...],
) -> dict[str, object]:
    """Return closest lexical anchor/eval pairs for manual review."""

    anchors = tuple(
        (profile.intent.identifier, question)
        for profile in catalog.profiles
        for question in profile.semantic_example_questions
    )
    pairs: list[dict[str, object]] = []
    for case in cases:
        closest_intent, closest_anchor, overlap = max(
            (
                (
                    intent_identifier,
                    anchor_question,
                    _token_overlap(case.question, anchor_question),
                )
                for intent_identifier, anchor_question in anchors
            ),
            key=lambda item: item[2],
        )
        pairs.append(
            {
                "eval_question": case.question,
                "closest_anchor_intent": closest_intent,
                "closest_anchor_question": closest_anchor,
                "normalized_token_overlap": overlap,
            }
        )
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "review": "manual_near_duplicate_review_required",
        "pairs": pairs,
    }


def write_tmp_json_report(path: str | Path, payload: dict[str, object]) -> None:
    """Write a calibration-side report only under /tmp."""

    report_path = _require_path(path, "report path")
    resolved = report_path.resolve()
    if not resolved.is_relative_to(_TMP_ROOT):
        raise SemanticIntentCalibrationError("report path must be inside /tmp")
    resolved.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


async def _embed_evaluation_questions(
    *,
    provider: EmbeddingProvider,
    embedding_model: str,
    cases: tuple[SemanticEvaluationCase, ...],
) -> tuple[EmbeddingVector, ...]:
    response = await provider.embed(
        EmbeddingRequest(
            model=embedding_model,
            inputs=tuple(case.question for case in cases),
        )
    )
    if len(response.embeddings) != len(cases):
        raise SemanticIntentCalibrationError(
            "embedding provider returned the wrong semantic evaluation count"
        )
    return response.embeddings


def _propose_threshold_for_intent(
    *,
    catalog: IntentCatalog,
    intent: QuestionIntent,
    cases: tuple[SemanticEvaluationCase, ...],
    scores_by_case: tuple[dict[str, float], ...],
) -> IntentThresholdProposal:
    profile = catalog.profile_for_intent(intent)
    positive_scores = tuple(
        scores[intent.identifier]
        for case, scores in zip(cases, scores_by_case, strict=True)
        if intent in case.expected_required_intents
    )
    candidate_thresholds = tuple(
        score
        for score in sorted(frozenset(positive_scores))
        if score >= profile.semantic_candidate_threshold
    )
    best_threshold: float | None = None
    best_support = 0
    best_false_positives = 0
    best_precision: float | None = None
    for threshold in candidate_thresholds:
        support = _true_positive_count(
            intent=intent,
            cases=cases,
            scores_by_case=scores_by_case,
            threshold=threshold,
        )
        false_positives = _false_positive_count(
            intent=intent,
            cases=cases,
            scores_by_case=scores_by_case,
            threshold=threshold,
        )
        precision = _precision(
            true_positives=support,
            false_positives=false_positives,
        )
        if (
            precision is not None
            and precision >= catalog.semantic_calibration.precision_floor
            and support >= catalog.semantic_calibration.minimum_required_support
        ):
            best_threshold = threshold
            best_support = support
            best_false_positives = false_positives
            best_precision = precision
            break
    if best_threshold is None:
        best_support = _true_positive_count(
            intent=intent,
            cases=cases,
            scores_by_case=scores_by_case,
            threshold=profile.semantic_candidate_threshold,
        )
        best_false_positives = _false_positive_count(
            intent=intent,
            cases=cases,
            scores_by_case=scores_by_case,
            threshold=profile.semantic_candidate_threshold,
        )
        best_precision = _precision(
            true_positives=best_support,
            false_positives=best_false_positives,
        )
    return IntentThresholdProposal(
        intent=intent,
        semantic_candidate_threshold=profile.semantic_candidate_threshold,
        proposed_semantic_required_threshold=best_threshold,
        positive_support=best_support,
        false_positive_count=best_false_positives,
        calibration_precision=best_precision,
    )


def _true_positive_count(
    *,
    intent: QuestionIntent,
    cases: tuple[SemanticEvaluationCase, ...],
    scores_by_case: tuple[dict[str, float], ...],
    threshold: float,
) -> int:
    return sum(
        1
        for case, scores in zip(cases, scores_by_case, strict=True)
        if intent in case.expected_required_intents
        and scores[intent.identifier] >= threshold
    )


def _false_positive_count(
    *,
    intent: QuestionIntent,
    cases: tuple[SemanticEvaluationCase, ...],
    scores_by_case: tuple[dict[str, float], ...],
    threshold: float,
) -> int:
    return sum(
        1
        for case, scores in zip(cases, scores_by_case, strict=True)
        if intent not in case.expected_required_intents
        and scores[intent.identifier] >= threshold
    )


def _precision(*, true_positives: int, false_positives: int) -> float | None:
    denominator = true_positives + false_positives
    if denominator == 0:
        return None
    return true_positives / denominator


def _load_case(
    value: object,
    index: int,
    catalog: IntentCatalog,
) -> SemanticEvaluationCase:
    case = _require_mapping(value, f"cases[{index}]")
    _require_exact_keys(case, _CASE_KEYS, f"cases[{index}]")
    language = _require_text(case["language"], f"cases[{index}].language")
    if language not in {"en", "it"}:
        raise SemanticIntentCalibrationError(
            f"cases[{index}].language must be en or it"
        )
    return SemanticEvaluationCase(
        question=_require_text(case["question"], f"cases[{index}].question"),
        language=language,
        expected_required_intents=tuple(
            catalog.intent_for_identifier(identifier)
            for identifier in _require_string_list(
                case["expected_required_intents"],
                f"cases[{index}].expected_required_intents",
            )
        ),
    )


def _token_overlap(left: str, right: str) -> float:
    left_tokens = frozenset(_normalized_text(left).split())
    right_tokens = frozenset(_normalized_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _require_path(value: str | Path, field_name: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value.strip())
    raise SemanticIntentCalibrationError(f"{field_name} must be set")


def _require_mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SemanticIntentCalibrationError(f"{field_name} must be an object")
    for key in value:
        if not isinstance(key, str):
            raise SemanticIntentCalibrationError(f"{field_name} keys must be strings")
    return cast(dict[str, object], value)


def _require_exact_keys(
    value: dict[str, object],
    expected_keys: frozenset[str],
    field_name: str,
) -> None:
    actual_keys = frozenset(value)
    extra_keys = actual_keys - expected_keys
    missing_keys = expected_keys - actual_keys
    if extra_keys:
        keys = ", ".join(sorted(extra_keys))
        raise SemanticIntentCalibrationError(f"{field_name} has unknown keys: {keys}")
    if missing_keys:
        keys = ", ".join(sorted(missing_keys))
        raise SemanticIntentCalibrationError(f"{field_name} is missing keys: {keys}")


def _require_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise SemanticIntentCalibrationError(f"{field_name} must be an array")
    return tuple(value)


def _require_string_list(value: object, field_name: str) -> tuple[str, ...]:
    values = _require_sequence(value, field_name)
    return tuple(
        _require_text(item, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    )


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticIntentCalibrationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
