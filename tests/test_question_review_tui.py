from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("textual")

from portfolio_rag_assistant.questions import QuestionReviewError
from portfolio_rag_assistant.questions import tui


def test_tui_event_id_parser_accepts_positive_integer_text() -> None:
    assert tui._event_id_from_text(" 42 ") == 42


@pytest.mark.parametrize("value", ("", "0", "-1", "abc"))
def test_tui_event_id_parser_rejects_invalid_text(value: str) -> None:
    with pytest.raises(QuestionReviewError, match="question event id must be positive"):
        tui._event_id_from_text(value)


def test_tui_optional_input_normalizes_blank_values() -> None:
    assert tui._optional_input_value("  alias  ") == "alias"
    assert tui._optional_input_value("  ") is None


def test_tui_runner_opens_review_app(monkeypatch) -> None:
    runs: list[FakeQuestionReviewStore] = []

    def fake_run(app: tui.QuestionReviewApp) -> None:
        runs.append(app._store)

    monkeypatch.setattr(tui.QuestionReviewApp, "run", fake_run)

    store = FakeQuestionReviewStore()
    tui.run_question_review_tui(store)

    assert runs == [store]


class FakeQuestionReviewStore:
    def list_events(self, *, state: str | None = None, limit: int = 50) -> tuple[Any, ...]:
        return ()
