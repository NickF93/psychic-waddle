from __future__ import annotations

from pathlib import Path

from portfolio_rag_assistant.api import ChatNoticeBody

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_SOURCE = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "src" / "portfolio_rag_assistant" / "questions").glob("*.py"))
)
API_SERVICE_SOURCE = (
    ROOT / "src" / "portfolio_rag_assistant" / "api" / "service.py"
).read_text(encoding="utf-8")
QUESTION_MIGRATION_SOURCE = (
    ROOT / "migrations" / "0002_question_events.sql"
).read_text(encoding="utf-8")


def test_question_collector_source_does_not_reference_runtime_metadata() -> None:
    normalized_source = QUESTIONS_SOURCE.lower()

    for forbidden in (
        "headers",
        "cookie",
        "session",
        "user_agent",
        "client",
        "language",
        "answer_status",
        "answer_text",
        "source_id",
        "retrieval_score",
        "request_metadata",
    ):
        assert forbidden not in normalized_source


def test_api_passes_only_question_text_to_collection_request() -> None:
    normalized_source = " ".join(API_SERVICE_SOURCE.split())

    call = "QuestionCollectionRequest(raw_question_text=request.question)"
    assert call in normalized_source
    collection_call_window = normalized_source[
        normalized_source.index(call) : normalized_source.index(call) + 140
    ]
    assert "language" not in collection_call_window


def test_question_recorded_notice_contains_only_machine_code() -> None:
    notice = ChatNoticeBody(code="question_recorded")

    assert notice.model_dump(mode="json") == {"code": "question_recorded"}


def test_question_event_migration_has_only_approved_review_columns() -> None:
    normalized_sql = QUESTION_MIGRATION_SOURCE.lower()

    for approved_column in (
        "id",
        "raw_question_text",
        "review_state",
        "review_category",
        "review_note",
        "created_at",
        "updated_at",
    ):
        assert approved_column in normalized_sql

    for forbidden_column in (
        "ip_address",
        "user_agent",
        "cookie",
        "session",
        "frontend_identifier",
        "language",
        "answer_text",
        "answer_status",
        "source_id",
        "source_kind",
        "retrieval_score",
        "request_metadata",
    ):
        assert forbidden_column not in normalized_sql
