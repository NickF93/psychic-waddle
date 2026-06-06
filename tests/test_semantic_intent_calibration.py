from __future__ import annotations

import asyncio
import json
from io import StringIO
from pathlib import Path

import pytest

from intent_catalog_helpers import TRACKED_INTENT_CATALOG, tracked_intent_catalog
from portfolio_rag_assistant import cli
from portfolio_rag_assistant.intent import (
    QuestionIntentProfileError,
    SemanticIntentCalibrationError,
    load_semantic_evaluation_cases,
    propose_semantic_thresholds,
    write_tmp_json_report,
)
from portfolio_rag_assistant.provider import EmbeddingRequest, EmbeddingResponse


def test_semantic_calibration_proposes_required_thresholds(
    tmp_path: Path,
) -> None:
    fixture = _write_fixture(
        tmp_path,
        (
            ("How would you summarize Niccolo for a recruiter?", ("professional_overview",)),
            ("Give me Niccolo's recruiter background.", ("professional_overview",)),
            ("What is his favorite pizza?", ()),
        ),
    )
    provider = FakeMappedEmbeddingProvider(_semantic_vectors(fixture))

    report = asyncio.run(
        propose_semantic_thresholds(
            catalog=tracked_intent_catalog(),
            provider=provider,
            embedding_model="nomic-embed-text",
            evaluation_path=fixture,
        )
    )

    overview = next(
        proposal
        for proposal in report.proposals
        if proposal.intent.identifier == "professional_overview"
    )
    assert overview.proposed_semantic_required_threshold == 1.0
    assert overview.positive_support == 2
    assert overview.false_positive_count == 0
    assert overview.calibration_precision == 1.0


def test_semantic_evaluation_loader_rejects_unknown_intents(
    tmp_path: Path,
) -> None:
    fixture = _write_fixture(
        tmp_path,
        (("Unsupported intent probe", ("not_an_intent",)),),
    )

    with pytest.raises(
        QuestionIntentProfileError,
        match="unsupported question intent: not_an_intent",
    ):
        load_semantic_evaluation_cases(
            path=fixture,
            catalog=tracked_intent_catalog(),
        )


def test_semantic_near_duplicate_report_writes_only_under_tmp(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SemanticIntentCalibrationError,
        match="report path must be inside /tmp",
    ):
        write_tmp_json_report(
            Path.cwd() / "intent-near-duplicates.json",
            {"schema_version": 1},
        )

    report_path = tmp_path / "intent-near-duplicates.json"
    write_tmp_json_report(report_path, {"schema_version": 1})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "schema_version": 1
    }


def test_intent_calibration_cli_outputs_proposals_without_catalog_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = _write_fixture(
        tmp_path,
        (
            ("How would you summarize Niccolo for a recruiter?", ("professional_overview",)),
            ("Give me Niccolo's recruiter background.", ("professional_overview",)),
            ("What is his favorite pizza?", ()),
        ),
    )
    near_duplicate_report = tmp_path / "near-duplicates.json"
    provider = FakeMappedEmbeddingProvider(_semantic_vectors(fixture))
    before_catalog = TRACKED_INTENT_CATALOG.read_text(encoding="utf-8")
    stdout = StringIO()

    monkeypatch.setattr(cli, "build_embedding_provider", lambda settings: provider)

    exit_code = cli.run(
        (
            "intent",
            "calibrate-semantic",
            "--evaluation",
            str(fixture),
            "--near-duplicate-report",
            str(near_duplicate_report),
        ),
        env={
            "EMBEDDING_BACKEND": "ollama",
            "EMBEDDING_BASE_URL": "http://localhost:11434/api",
            "EMBEDDING_MODEL": "nomic-embed-text",
            "INTENT_PROFILES_PATH": str(TRACKED_INTENT_CATALOG),
        },
        stdout=stdout,
    )

    output = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert output["catalog_write"] == "manual_review_required"
    assert near_duplicate_report.exists()
    assert TRACKED_INTENT_CATALOG.read_text(encoding="utf-8") == before_catalog


def _write_fixture(
    tmp_path: Path,
    cases: tuple[tuple[str, tuple[str, ...]], ...],
) -> Path:
    path = tmp_path / "semantic-evaluation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "question": question,
                        "language": "en",
                        "expected_required_intents": list(expected_intents),
                    }
                    for question, expected_intents in cases
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _semantic_vectors(path: Path) -> dict[str, tuple[float, ...]]:
    vectors: dict[str, tuple[float, ...]] = {}
    for profile in tracked_intent_catalog().profiles:
        vector = (
            (1.0, 0.0)
            if profile.intent.identifier == "professional_overview"
            else (-1.0, 0.0)
        )
        for question in profile.semantic_example_questions:
            vectors[question] = vector
    payload = json.loads(path.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        vectors[case["question"]] = (
            (1.0, 0.0)
            if "professional_overview" in case["expected_required_intents"]
            else (-1.0, 0.0)
        )
    return vectors


class FakeMappedEmbeddingProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors = vectors
        self.requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests = (*self.requests, request)
        return EmbeddingResponse(
            model=request.model,
            embeddings=tuple(self._vectors[item] for item in request.inputs),
        )
