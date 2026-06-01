from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any

from portfolio_rag_assistant import cli
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from portfolio_rag_assistant.questions import QuestionEvent


def test_ingest_command_validates_input_before_database_connection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [],
                "facts": [],
            }
        ),
        encoding="utf-8",
    )
    called = False

    def fail_connect_database(**kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError(kwargs)

    monkeypatch.setattr(cli, "connect_database", fail_connect_database)
    stderr = StringIO()

    exit_code = cli.run(
        ("knowledge", "ingest", str(invalid_path)),
        env=_db_env(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert called is False
    assert "sources must not be empty" in stderr.getvalue()


def test_validate_command_does_not_require_database_or_provider_config(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.run(
        ("knowledge", "validate", str(valid_path)),
        env={},
        stdout=stdout,
    )

    assert exit_code == 0
    assert "validated 1 sources, 1 facts, 1 chunks" in stdout.getvalue()


def test_ingest_command_requires_database_settings_after_valid_input(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "knowledge.json"
    valid_path.write_text(json.dumps(_valid_document()), encoding="utf-8")
    stderr = StringIO()

    exit_code = cli.run(("knowledge", "ingest", str(valid_path)), env={}, stderr=stderr)

    assert exit_code == 2
    assert "DB_HOST must be set" in stderr.getvalue()


def test_runtime_smoke_checks_database_and_providers(monkeypatch) -> None:
    connection = FakeSmokeConnection()
    chat_provider = FakeChatProvider()
    embedding_provider = FakeEmbeddingProvider()
    stdout = StringIO()

    monkeypatch.setattr(cli, "connect_database", lambda **kwargs: connection)
    monkeypatch.setattr(cli, "build_chat_provider", lambda settings: chat_provider)
    monkeypatch.setattr(
        cli,
        "build_embedding_provider",
        lambda settings: embedding_provider,
    )

    exit_code = cli.run(
        ("runtime", "smoke"),
        env={
            **_db_env(),
            "CHAT_BACKEND": "openai-compatible",
            "CHAT_BASE_URL": "https://api.example.test/v1",
            "CHAT_MODEL": "chat-model",
            "EMBEDDING_BACKEND": "ollama",
            "EMBEDDING_BASE_URL": "http://localhost:11434/api",
            "EMBEDDING_MODEL": "nomic-embed-text",
        },
        stdout=stdout,
    )

    assert exit_code == 0
    assert "runtime smoke passed" in stdout.getvalue()
    assert connection.entered is True
    assert chat_provider.requests == (
        ChatRequest(
            model="chat-model",
            messages=(ChatMessage(role="user", content="Reply with OK."),),
            temperature=0.0,
            max_tokens=8,
        ),
    )
    assert embedding_provider.requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("runtime smoke",)),
    )


def test_questions_list_uses_review_store(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=(_question_event(11),))
    rendered: list[tuple[QuestionEvent, ...]] = []

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))
    monkeypatch.setattr(
        cli,
        "_print_question_table",
        lambda events, stdout: rendered.append(events),
    )

    exit_code = cli.run(
        ("questions", "list", "--state", "pending", "--limit", "5"),
        env=_db_env(),
    )

    assert exit_code == 0
    assert store.list_calls == (("pending", 5),)
    assert rendered == [(_question_event(11),)]


def test_questions_show_uses_review_store(monkeypatch) -> None:
    event = _question_event(12)
    store = FakeQuestionReviewStore(events=(event,))
    rendered: list[QuestionEvent] = []

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))
    monkeypatch.setattr(
        cli,
        "_print_question_detail",
        lambda question_event, stdout: rendered.append(question_event),
    )

    exit_code = cli.run(("questions", "show", "12"), env=_db_env())

    assert exit_code == 0
    assert store.get_calls == (12,)
    assert rendered == [event]


def test_questions_mark_updates_operator_fields(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=(_question_event(13, state="reviewed"),))
    stdout = StringIO()

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))

    exit_code = cli.run(
        (
            "questions",
            "mark",
            "13",
            "--state",
            "reviewed",
            "--category",
            "missing_fact",
            "--note",
            "Add reviewed public source.",
        ),
        env=_db_env(),
        stdout=stdout,
    )

    assert exit_code == 0
    assert store.mark_calls == (
        (13, "reviewed", "missing_fact", "Add reviewed public source."),
    )
    assert "marked question event 13 as reviewed" in stdout.getvalue()


def test_questions_delete_deletes_raw_record(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=())
    stdout = StringIO()

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))

    exit_code = cli.run(
        ("questions", "delete", "14"),
        env=_db_env(),
        stdout=stdout,
    )

    assert exit_code == 0
    assert store.delete_calls == (14,)
    assert "deleted question event 14" in stdout.getvalue()


def test_questions_delete_reports_missing_record(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=(), delete_result=False)
    stderr = StringIO()

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))

    exit_code = cli.run(
        ("questions", "delete", "14"),
        env=_db_env(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert "question event not found" in stderr.getvalue()


def test_questions_export_writes_jsonl(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=(_question_event(15),))
    stdout = StringIO()

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))

    exit_code = cli.run(
        ("questions", "export", "--state", "pending"),
        env=_db_env(),
        stdout=stdout,
    )

    assert exit_code == 0
    assert store.export_calls == ("pending",)
    assert json.loads(stdout.getvalue()) == {
        "id": 15,
        "raw_question_text": "Could Niccolo answer this?",
        "review_state": "pending",
        "review_category": None,
        "review_note": None,
        "created_at": "2026-06-01T12:00:00+00:00",
        "updated_at": "2026-06-01T12:00:00+00:00",
    }


def test_questions_review_opens_terminal_review_mode(monkeypatch) -> None:
    store = FakeQuestionReviewStore(events=())
    opened: list[FakeQuestionReviewStore] = []

    monkeypatch.setattr(cli, "_question_review_store", lambda env: FakeStoreContext(store))
    monkeypatch.setattr(
        cli,
        "_run_question_review_tui",
        lambda review_store: opened.append(review_store),
    )

    exit_code = cli.run(("questions", "review"), env=_db_env())

    assert exit_code == 0
    assert opened == [store]


def _valid_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sources": [
            {
                "source_uri": "cv://niccolo/main",
                "title": "Niccolo Ferrari CV",
                "reviewed_at": "2026-05-28T00:00:00+00:00",
            }
        ],
        "facts": [
            {
                "source_uri": "cv://niccolo/main",
                "category": "experience",
                "fact_text": "Niccolo worked at NAIS s.r.l.",
                "source_locator": "Experience section",
                "public_visible": True,
            }
        ],
    }


def _db_env() -> dict[str, str]:
    return {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "portfolio",
        "DB_USER": "portfolio_user",
        "DB_PASSWORD": "secret",
    }


class FakeCursor:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...]:
        return self._row


class FakeSmokeConnection:
    def __init__(self) -> None:
        self.entered = False

    def __enter__(self) -> FakeSmokeConnection:
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> FakeCursor:
        if "to_regclass" in query:
            return FakeCursor((True, True, True, True))
        if "FROM chunk_embeddings" in query:
            return FakeCursor((True,))
        raise AssertionError(query)


class FakeChatProvider:
    def __init__(self) -> None:
        self.requests: tuple[ChatRequest, ...] = ()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests = (*self.requests, request)
        return ChatResponse(
            model=request.model,
            message=ChatMessage(role="assistant", content="OK"),
        )


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests = (*self.requests, request)
        return EmbeddingResponse(model=request.model, embeddings=((1.0,),))


def _question_event(event_id: int, *, state: str = "pending") -> QuestionEvent:
    return QuestionEvent(
        id=event_id,
        raw_question_text="Could Niccolo answer this?",
        review_state=state,
        review_category=None,
        review_note=None,
        created_at="2026-06-01T12:00:00+00:00",
        updated_at="2026-06-01T12:00:00+00:00",
    )


class FakeStoreContext:
    def __init__(self, store: "FakeQuestionReviewStore") -> None:
        self._store = store

    def __enter__(self) -> "FakeQuestionReviewStore":
        return self._store

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeQuestionReviewStore:
    def __init__(
        self,
        *,
        events: tuple[QuestionEvent, ...],
        delete_result: bool = True,
    ) -> None:
        self._events = events
        self._delete_result = delete_result
        self.list_calls: tuple[tuple[str | None, int], ...] = ()
        self.get_calls: tuple[int, ...] = ()
        self.mark_calls: tuple[tuple[int, str, str | None, str | None], ...] = ()
        self.delete_calls: tuple[int, ...] = ()
        self.export_calls: tuple[str | None, ...] = ()

    def list_events(
        self,
        *,
        state: str | None = None,
        limit: int = 50,
    ) -> tuple[QuestionEvent, ...]:
        self.list_calls = (*self.list_calls, (state, limit))
        return self._events

    def get_event(self, event_id: int) -> QuestionEvent:
        self.get_calls = (*self.get_calls, event_id)
        return self._events[0]

    def mark_event(
        self,
        event_id: int,
        *,
        state: str,
        category: str | None,
        note: str | None,
    ) -> QuestionEvent:
        self.mark_calls = (*self.mark_calls, (event_id, state, category, note))
        return _question_event(event_id, state=state)

    def delete_event(self, event_id: int) -> bool:
        self.delete_calls = (*self.delete_calls, event_id)
        return self._delete_result

    def export_events(self, *, state: str | None = None) -> tuple[QuestionEvent, ...]:
        self.export_calls = (*self.export_calls, state)
        return self._events
