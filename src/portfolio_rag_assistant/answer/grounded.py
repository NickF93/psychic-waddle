"""Grounded answer generation with deterministic source handling."""

from __future__ import annotations

from portfolio_rag_assistant.answer.contract import (
    AnswerGenerationConfigurationError,
    AnswerGenerationProviderError,
    AnswerGenerationRequest,
    AnswerGenerationResponse,
    AnswerLanguage,
    AnswerSourceReference,
)
from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NEEDS_CLARIFICATION,
    NOT_ANSWERABLE,
)
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    LLMProvider,
    LLMProviderError,
)
from portfolio_rag_assistant.retrieval import RetrievedContext

_SYSTEM_PROMPT = """\
You write concise, professional answers for a recruiter.
Use only the approved context provided by the application.
Do not use outside knowledge.
Do not infer facts, dates, employers, degrees, skills, private information, or
source evidence that are absent from the approved context.
If the approved context is insufficient, say that the available verified context
is not enough.
Do not mention retrieval scores, ranking, thresholds, or internal diagnostics.
Do not add citations or source labels. The application attaches sources
deterministically.
Answer in the requested language.
"""

_LANGUAGE_NAMES: dict[AnswerLanguage, str] = {
    "en": "English",
    "it": "Italian",
}

_FALLBACK_TEXT: dict[AnswerLanguage, str] = {
    "en": "I do not have verified public context to answer that reliably.",
    "it": "Non ho contesto pubblico verificato per rispondere in modo affidabile.",
}

_CLARIFICATION_TEXT: dict[AnswerLanguage, str] = {
    "en": (
        "I can answer that, but I need a more specific question about "
        "experience, education, projects, research, skills, or contact details."
    ),
    "it": (
        "Posso rispondere, ma ho bisogno di una domanda piu specifica su "
        "esperienza, formazione, progetti, ricerca, competenze o contatti."
    ),
}


class GroundedAnswerGenerator:
    """Generate final wording from already approved retrieved context."""

    def __init__(
        self,
        provider: LLMProvider,
        chat_model: str,
        *,
        max_tokens: int = 384,
    ) -> None:
        if not isinstance(provider, LLMProvider):
            raise AnswerGenerationConfigurationError(
                "provider must satisfy LLMProvider"
            )
        _require_non_empty_text(chat_model, "chat_model")
        _require_positive_int(max_tokens, "max_tokens")
        self._provider = provider
        self._chat_model = chat_model
        self._max_tokens = max_tokens

    async def generate(
        self,
        request: AnswerGenerationRequest,
    ) -> AnswerGenerationResponse:
        """Return final answer text with code-owned source evidence."""

        if request.decision.status == NOT_ANSWERABLE:
            return AnswerGenerationResponse(
                answer_text=_FALLBACK_TEXT[request.language],
                status=NOT_ANSWERABLE,
            )
        if request.decision.status == NEEDS_CLARIFICATION:
            return AnswerGenerationResponse(
                answer_text=_CLARIFICATION_TEXT[request.language],
                status=NEEDS_CLARIFICATION,
            )

        sources = _source_references_from_context(request.decision.approved_context)
        chat_request = ChatRequest(
            model=self._chat_model,
            messages=(
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(role="user", content=_user_prompt(request)),
            ),
            temperature=0.0,
            max_tokens=self._max_tokens,
        )

        try:
            chat_response = await self._provider.chat(chat_request)
        except LLMProviderError as error:
            raise AnswerGenerationProviderError("provider chat failed") from error

        return AnswerGenerationResponse(
            answer_text=_with_source_note(
                chat_response.message.content.strip(),
                sources,
                request.language,
            ),
            status=ANSWERABLE,
            sources=sources,
        )


def _user_prompt(request: AnswerGenerationRequest) -> str:
    context_blocks = tuple(
        _context_block(index, context)
        for index, context in enumerate(request.decision.approved_context, start=1)
    )
    return "\n\n".join(
        (
            f"Requested language: {_LANGUAGE_NAMES[request.language]}",
            f"Question: {request.question.strip()}",
            "Approved context:",
            *context_blocks,
        )
    )


def _context_block(index: int, context: RetrievedContext) -> str:
    lines = [
        f"[{index}]",
        f"Category: {context.category}",
        f"Source title: {context.source_title}",
    ]
    if context.source_locator is not None:
        lines.append(f"Source locator: {context.source_locator}")
    lines.append(f"Text: {context.chunk_text}")
    return "\n".join(lines)


def _source_references_from_context(
    contexts: tuple[RetrievedContext, ...],
) -> tuple[AnswerSourceReference, ...]:
    seen: set[tuple[str, str, str | None]] = set()
    sources: list[AnswerSourceReference] = []
    for context in contexts:
        key = (context.source_title, context.source_uri, context.source_locator)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            AnswerSourceReference(
                source_title=context.source_title,
                source_uri=context.source_uri,
                source_locator=context.source_locator,
            )
        )
    return tuple(sources)


def _with_source_note(
    answer_text: str,
    sources: tuple[AnswerSourceReference, ...],
    language: AnswerLanguage,
) -> str:
    return f"{answer_text}\n\n{_source_note(sources, language)}"


def _source_note(
    sources: tuple[AnswerSourceReference, ...],
    language: AnswerLanguage,
) -> str:
    label = "Sources" if language == "en" else "Fonti"
    formatted_sources = "; ".join(_format_source(source) for source in sources)
    return f"{label}: {formatted_sources}."


def _format_source(source: AnswerSourceReference) -> str:
    if source.source_locator is None:
        return source.source_title
    return f"{source.source_title} ({source.source_locator})"


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AnswerGenerationConfigurationError(
            f"{field_name} must be a non-empty string"
        )


def _require_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AnswerGenerationConfigurationError(
            f"{field_name} must be a positive integer"
        )
