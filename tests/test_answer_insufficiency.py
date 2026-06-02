from __future__ import annotations

import pytest

from portfolio_rag_assistant.answer.insufficiency import (
    is_insufficient_context_answer,
)


@pytest.mark.parametrize(
    "answer_text",
    (
        "INSUFFICIENT_APPROVED_CONTEXT",
        "  insufficient_approved_context.  ",
        "The approved context is insufficient to answer that.",
        "The available verified context is not enough to determine that.",
        "The approved context does not provide information on that topic.",
        "I don't have enough context to answer that reliably.",
        "I cannot determine that from the approved context.",
        "I cannot answer from the approved context.",
        "I don't have enough context, but I can answer if more context is added.",
        "Non ho contesto pubblico verificato per rispondere.",
        "Il contesto non è sufficiente per rispondere.",
        "Non ho abbastanza contesto, ma posso rispondere se aggiungi contesto.",
    ),
)
def test_insufficiency_guard_detects_whole_answer_refusals(
    answer_text: str,
) -> None:
    assert is_insufficient_context_answer(answer_text) is True


@pytest.mark.parametrize(
    "answer_text",
    (
        (
            "The CV does not mention a PhD in Physics, but it states that "
            "Niccolo completed a Ph.D. in Computer Science Engineering."
        ),
        (
            "The approved context does not provide his favorite pizza topping, "
            "but it lists interests including artificial intelligence, game "
            "development, climbing, books, films, and cacti cultivation."
        ),
        (
            "I cannot determine the favorite pizza topping from the approved "
            "context, but the CV lists interests including artificial "
            "intelligence and game development."
        ),
        (
            "Il CV non menziona un dottorato in fisica, ma riporta un Ph.D. "
            "in Computer Science Engineering."
        ),
        (
            "Il contesto approvato non fornisce il gusto di pizza preferito, "
            "tuttavia il CV menziona interessi come intelligenza artificiale "
            "e game development."
        ),
    ),
)
def test_insufficiency_guard_keeps_grounded_contrastive_answers(
    answer_text: str,
) -> None:
    assert is_insufficient_context_answer(answer_text) is False
