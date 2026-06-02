"""Provider wording consistency checks for approved answer generation."""

from __future__ import annotations

_INSUFFICIENT_CONTEXT_SENTINEL = "INSUFFICIENT_APPROVED_CONTEXT"

_REFUSAL_PATTERNS = (
    "approved context is insufficient",
    "approved context does not contain enough information",
    "approved context does not provide information",
    "available verified context is not enough",
    "cannot answer from the approved context",
    "cannot determine",
    "can't answer from the approved context",
    "can't determine",
    "context is not enough",
    "context does not provide information",
    "do not have enough context",
    "do not have enough information",
    "do not have verified public context",
    "don't have enough context",
    "don't have enough information",
    "i cannot answer",
    "insufficient context",
    "not enough context",
    "not enough information",
    "non abbastanza informazioni",
    "non ho abbastanza contesto",
    "non ho contesto pubblico verificato",
    "contesto insufficiente",
    "contesto non e sufficiente",
    "contesto non è sufficiente",
)

_AFFIRMATIVE_CONTINUATION_PATTERNS = (
    "approved context lists",
    "approved context mentions",
    "approved context states",
    "context lists",
    "context mentions",
    "context states",
    "cv lists",
    "cv mentions",
    "cv states",
    "it lists",
    "it mentions",
    "it states",
    "lists",
    "mentions",
    "states that",
    "il contesto indica",
    "il contesto menziona",
    "il contesto riporta",
    "il cv indica",
    "il cv menziona",
    "il cv riporta",
    "indica che",
    "menziona",
    "riporta",
)

_WORD_PUNCTUATION = str.maketrans(
    {character: " " for character in ".,!?;:()[]{}\"'`"}
)


def is_insufficient_context_answer(answer_text: str) -> bool:
    """Return true when provider output is a whole-answer insufficiency."""

    normalized = _normalize_spaces(answer_text)
    if _INSUFFICIENT_CONTEXT_SENTINEL.casefold() in _strip_boundary_punctuation(
        normalized
    ):
        return True

    word_text = _normalize_words(answer_text)
    if not _contains_any_pattern(word_text, _REFUSAL_PATTERNS):
        return False

    return not _contains_any_pattern(
        word_text,
        _AFFIRMATIVE_CONTINUATION_PATTERNS,
    )


def _contains_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(_contains_pattern(text, pattern) for pattern in patterns)


def _contains_pattern(text: str, pattern: str) -> bool:
    normalized_pattern = _normalize_words(pattern)
    return f" {normalized_pattern} " in f" {text} "


def _normalize_spaces(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_words(value: str) -> str:
    return _normalize_spaces(value.translate(_WORD_PUNCTUATION))


def _strip_boundary_punctuation(value: str) -> str:
    return value.strip(" \t\r\n.!?;:'\"`")
