"""Grounded answer generation with deterministic source handling."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import aclosing
from dataclasses import replace

from portfolio_rag_assistant.answer.delivery import (
    GenerationTarget,
    ProvisionalText,
    failure_reason,
)
from portfolio_rag_assistant.answer.contract import AnswerDelta, GenerationStatus
from portfolio_rag_assistant.provider.contract import StreamingChatProvider

LOGGER = logging.getLogger(__name__)

from portfolio_rag_assistant.answer.contract import (
    AnswerGenerationConfigurationError,
    AnswerGenerationProviderError,
    AnswerGenerationRequest,
    AnswerGenerationResponse,
    AnswerLanguage,
    AnswerSourceReference,
)
from portfolio_rag_assistant.answer.insufficiency import (
    is_insufficient_context_answer,
)
from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NEEDS_CLARIFICATION,
    NOT_ANSWERABLE,
)
from portfolio_rag_assistant.provider import (
    ChatProvider,
    ChatMessage,
    ChatRequest,
    LLMProviderError,
)
from portfolio_rag_assistant.retrieval import RetrievedContext

_SYSTEM_PROMPT = """\
You write concise, professional answers for a recruiter.
Use only the approved context provided by the application.
Do not use outside knowledge.
Do not infer facts, dates, employers, degrees, skills, private information, or
source evidence that are absent from the approved context.
If you cannot answer directly from the approved context, reply exactly:
INSUFFICIENT_APPROVED_CONTEXT
Do not mention retrieval scores, ranking, thresholds, or internal diagnostics.
Do not add citations or source labels. The application attaches sources
deterministically.
When comparing works or projects, give each item its own short bullet. Preserve
each item's individual submission, review, acceptance and release status.
Never transfer or generalize a status from one item to another.
For fit or suitability questions, summarize approved evidence only. Do not give
a yes/no hiring verdict, hiring recommendation, or prediction.
Answer in the requested language.
Use Markdown paragraphs and proper newline-separated bullets for lists.
Do not flatten a list into one line separated by hyphens.
Keep the complete answer under 120 words. Summarize only facts that directly
answer the question; do not repeat the full context.
For experience or employer questions, include each relevant employer in the
approved context. Keep current and past roles distinct and never transfer dates
or responsibilities between roles. Use one short bullet per employer.
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
        provider: ChatProvider,
        chat_model: str,
        *,
        max_tokens: int = 384,
        primary_timeout: float = 15.0,
        fallback_provider: ChatProvider | None = None,
        fallback_model: str | None = None,
        fallback_timeout: float = 180.0,
        fallback_max_tokens: int = 384,
    ) -> None:
        if not isinstance(provider, ChatProvider):
            raise AnswerGenerationConfigurationError(
                "provider must satisfy ChatProvider"
            )
        _require_non_empty_text(chat_model, "chat_model")
        _require_positive_int(max_tokens, "max_tokens")
        self._provider = provider
        self._chat_model = chat_model
        self._max_tokens = max_tokens
        self._targets = (
            GenerationTarget(
                provider, chat_model, primary_timeout, "primary", max_tokens
            ),
        )
        if (fallback_provider is None) != (fallback_model is None):
            raise AnswerGenerationConfigurationError(
                "fallback provider and model must be configured together"
            )
        if fallback_provider is not None:
            self._targets += (
                GenerationTarget(
                    fallback_provider,
                    fallback_model,
                    fallback_timeout,
                    "fallback",
                    fallback_max_tokens,
                ),
            )

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

        for index, target in enumerate(self._targets):
            started = time.monotonic()
            LOGGER.info("Generation started: provider=%s", target.role)
            try:
                async with asyncio.timeout(target.timeout):
                    chat_response = await target.provider.chat(
                        replace(
                            chat_request,
                            model=target.model,
                            max_tokens=target.max_tokens,
                        )
                    )
                LOGGER.info(
                    "Generation completed: provider=%s elapsed=%.3fs",
                    target.role,
                    time.monotonic() - started,
                )
                break
            except (LLMProviderError, TimeoutError) as error:
                LOGGER.warning(
                    "Generation failed: provider=%s reason=%s elapsed=%.3fs",
                    target.role,
                    failure_reason(error),
                    time.monotonic() - started,
                )
                if index == len(self._targets) - 1:
                    raise AnswerGenerationProviderError(
                        "provider chat failed"
                    ) from error

        answer_text = chat_response.message.content.strip()
        if is_insufficient_context_answer(answer_text):
            return AnswerGenerationResponse(
                answer_text=_FALLBACK_TEXT[request.language],
                status=NOT_ANSWERABLE,
            )

        return AnswerGenerationResponse(
            answer_text=_with_source_note(
                answer_text,
                sources,
                request.language,
            ),
            status=ANSWERABLE,
            sources=sources,
        )

    async def stream(self, request: AnswerGenerationRequest):
        """Stream provisional text, then exactly one classified completion."""
        if request.decision.status != ANSWERABLE:
            yield await self.generate(request)
            return
        sources = _source_references_from_context(request.decision.approved_context)
        visible = False
        for index, target in enumerate(self._targets):
            if not isinstance(target.provider, StreamingChatProvider):
                raise AnswerGenerationConfigurationError(
                    "configured provider does not support streaming"
                )
            yield GenerationStatus(target.role)
            started = time.monotonic()
            LOGGER.info("Generation stream started: provider=%s", target.role)
            guard = ProvisionalText()
            provider_request = ChatRequest(
                model=target.model,
                messages=(
                    ChatMessage(role="system", content=_SYSTEM_PROMPT),
                    ChatMessage(role="user", content=_user_prompt(request)),
                ),
                temperature=0.0,
                max_tokens=target.max_tokens,
            )
            try:
                leading = ""
                async with aclosing(
                    target.provider.stream_chat(provider_request)
                ) as stream:
                    while True:
                        # Bound upstream inactivity, never the consumer's work.
                        async with asyncio.timeout(target.timeout):
                            chunk = await anext(stream, None)
                        if chunk is None:
                            break
                        text = guard.add(chunk)
                        if not visible:
                            leading += text
                            if not leading.strip():
                                continue
                            text, leading = leading, ""
                            LOGGER.info(
                                "First answer text: provider=%s elapsed=%.3fs",
                                target.role,
                                time.monotonic() - started,
                            )
                            visible = True
                        if text:
                            yield AnswerDelta(text)
                if not guard.text.strip():
                    raise LLMProviderError("provider returned no answer text")
                if is_insufficient_context_answer(guard.text):
                    result = AnswerGenerationResponse(
                        answer_text=_FALLBACK_TEXT[request.language],
                        status=NOT_ANSWERABLE,
                    )
                else:
                    tail = guard.add("", final=True)
                    if tail:
                        yield AnswerDelta(tail)
                    result = AnswerGenerationResponse(
                        answer_text=_with_source_note(
                            guard.text.strip(), sources, request.language
                        ),
                        status=ANSWERABLE,
                        sources=sources,
                    )
                LOGGER.info(
                    "Generation stream completed: provider=%s elapsed=%.3fs",
                    target.role,
                    time.monotonic() - started,
                )
                yield result
                return
            except (LLMProviderError, TimeoutError) as error:
                LOGGER.warning(
                    "Generation stream failed: provider=%s reason=%s elapsed=%.3fs partial=%s",
                    target.role,
                    failure_reason(error),
                    time.monotonic() - started,
                    visible,
                )
                if visible or index == len(self._targets) - 1:
                    raise AnswerGenerationProviderError(
                        "generation interrupted"
                        if visible
                        else "generation unavailable"
                    ) from error
            except asyncio.CancelledError:
                LOGGER.info(
                    "Generation stream cancelled: provider=%s elapsed=%.3fs",
                    target.role,
                    time.monotonic() - started,
                )
                raise


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
