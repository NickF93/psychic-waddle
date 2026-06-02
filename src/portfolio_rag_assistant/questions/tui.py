"""Terminal review UI for collected unanswered questions."""

from __future__ import annotations

from typing import Final

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from portfolio_rag_assistant.questions.review import (
    QUESTION_REVIEW_CATEGORIES,
    QuestionReviewError,
    QuestionReviewStore,
)

_TABLE_ID: Final[str] = "questions-table"
_EVENT_ID_ID: Final[str] = "event-id"
_CATEGORY_ID: Final[str] = "category"
_NOTE_ID: Final[str] = "review-note"
_STATUS_ID: Final[str] = "status"


class QuestionReviewApp(App[None]):
    """Small operator TUI for manually reviewing raw unanswered questions."""

    CSS = """
    #questions-table {
        height: 1fr;
    }

    #review-form {
        height: auto;
        padding: 1 2;
    }

    #review-actions {
        height: auto;
        padding-top: 1;
    }

    #status {
        height: auto;
        padding: 0 2 1 2;
    }
    """
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, store: QuestionReviewStore, *, limit: int = 100) -> None:
        super().__init__()
        self._store = store
        self._limit = limit

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id=_TABLE_ID)
        with Vertical(id="review-form"):
            yield Label("Question ID")
            yield Input(placeholder="Required event id", id=_EVENT_ID_ID)
            yield Label("Category")
            yield Input(
                placeholder=", ".join(sorted(QUESTION_REVIEW_CATEGORIES)),
                id=_CATEGORY_ID,
            )
            yield Label("Review note")
            yield Input(placeholder="Optional operator note", id=_NOTE_ID)
            with Horizontal(id="review-actions"):
                yield Button("Reviewed", id="mark-reviewed", variant="success")
                yield Button("Ignored", id="mark-ignored", variant="warning")
                yield Button("Delete", id="delete-event", variant="error")
                yield Button("Refresh", id="refresh-events")
        yield Static("", id=_STATUS_ID)
        yield Footer()

    def on_mount(self) -> None:
        table = self._table()
        table.add_columns("ID", "State", "Category", "Created", "Question")
        self._refresh_events()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mark-reviewed":
            self._mark_event("reviewed")
            return
        if event.button.id == "mark-ignored":
            self._mark_event("ignored")
            return
        if event.button.id == "delete-event":
            self._delete_event()
            return
        if event.button.id == "refresh-events":
            self._refresh_events()

    def action_refresh(self) -> None:
        self._refresh_events()

    def _refresh_events(self) -> None:
        try:
            events = self._store.list_events(limit=self._limit)
        except QuestionReviewError as error:
            self._set_status(f"error: {error}")
            return

        table = self._table()
        table.clear()
        for question_event in events:
            table.add_row(
                str(question_event.id),
                question_event.review_state,
                question_event.review_category or "",
                question_event.created_at,
                question_event.raw_question_text,
            )
        self._set_status(f"loaded {len(events)} question events")

    def _mark_event(self, state: str) -> None:
        try:
            event = self._store.mark_event(
                _event_id_from_text(self._input_value(_EVENT_ID_ID)),
                state=state,
                category=_optional_input_value(self._input_value(_CATEGORY_ID)),
                note=_optional_input_value(self._input_value(_NOTE_ID)),
            )
        except QuestionReviewError as error:
            self._set_status(f"error: {error}")
            return

        self._set_status(f"marked question event {event.id} as {event.review_state}")
        self._refresh_events()

    def _delete_event(self) -> None:
        try:
            event_id = _event_id_from_text(self._input_value(_EVENT_ID_ID))
            deleted = self._store.delete_event(event_id)
        except QuestionReviewError as error:
            self._set_status(f"error: {error}")
            return

        if deleted:
            self._set_status(f"deleted question event {event_id}")
            self._refresh_events()
            return
        self._set_status("error: question event not found")

    def _input_value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value

    def _table(self) -> DataTable:
        return self.query_one(f"#{_TABLE_ID}", DataTable)

    def _set_status(self, message: str) -> None:
        self.query_one(f"#{_STATUS_ID}", Static).update(message)


def run_question_review_tui(store: QuestionReviewStore) -> None:
    """Open the local terminal review application."""

    QuestionReviewApp(store).run()


def _event_id_from_text(value: str) -> int:
    text = value.strip()
    if not text.isdecimal():
        raise QuestionReviewError("question event id must be positive")
    event_id = int(text)
    if event_id <= 0:
        raise QuestionReviewError("question event id must be positive")
    return event_id


def _optional_input_value(value: str) -> str | None:
    text = value.strip()
    return text or None
