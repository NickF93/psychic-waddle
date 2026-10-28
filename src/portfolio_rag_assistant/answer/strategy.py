"""Bounded generation delivery, independent of evidence and source selection."""

import asyncio
import logging
import time
from contextlib import aclosing
from dataclasses import dataclass

from portfolio_rag_assistant.provider.contract import (
    ChatRequest,
    LLMInputBudgetError,
    LLMProviderError,
    StreamingChatProvider,
)

from .contract import (
    AnswerDelta,
    AnswerGenerationConfigurationError,
    AnswerGenerationProviderError,
    GenerationStatus,
)
from .delivery import failure_reason
from .visibility import has_visible_answer_text

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedText:
    text: str


class GenerationStrategy:
    """One primary and at most one explicit fallback before visible content."""

    def __init__(self, targets):
        self.targets = targets

    @staticmethod
    def _request(target, messages):
        request = ChatRequest(
            model=target.model,
            messages=messages,
            **{**target.options, "max_tokens": target.max_tokens},
        )
        target.input_budget.check(request)
        return request

    async def generate(self, messages):
        for index, target in enumerate(self.targets):
            started = time.monotonic()
            LOGGER.info("Generation started: provider=%s", target.role)
            try:
                request = self._request(target, messages)
                async with asyncio.timeout(target.timeout):
                    result = await target.provider.chat(request)
                LOGGER.info(
                    "Generation completed: provider=%s elapsed=%.3fs",
                    target.role,
                    time.monotonic() - started,
                )
                return result
            except (LLMProviderError, TimeoutError) as error:
                LOGGER.warning(
                    "Generation failed: provider=%s reason=%s elapsed=%.3fs",
                    target.role,
                    failure_reason(error),
                    time.monotonic() - started,
                )
                if index == len(self.targets) - 1:
                    if isinstance(error, LLMInputBudgetError):
                        raise
                    raise AnswerGenerationProviderError(
                        "provider chat failed"
                    ) from error

    async def stream(self, messages, *, gate_factory):
        visible = False
        for index, target in enumerate(self.targets):
            if not isinstance(target.provider, StreamingChatProvider):
                raise AnswerGenerationConfigurationError(
                    "configured provider does not support streaming"
                )
            yield GenerationStatus(target.role)
            started = time.monotonic()
            LOGGER.info("Generation stream started: provider=%s", target.role)
            gate = gate_factory()
            try:
                request = self._request(target, messages)
                leading = ""
                async with aclosing(target.provider.stream_chat(request)) as stream:
                    while True:
                        async with asyncio.timeout(target.timeout):
                            chunk = await anext(stream, None)
                        if chunk is None:
                            break
                        text = gate.add(chunk)
                        if not visible:
                            leading += text
                            if not has_visible_answer_text(leading):
                                continue
                            text, leading = leading, ""
                            visible = True
                            LOGGER.info(
                                "First answer text: provider=%s elapsed=%.3fs",
                                target.role,
                                time.monotonic() - started,
                            )
                        if text:
                            yield AnswerDelta(text)
                tail = gate.add("", final=True)
                if not visible:
                    leading += tail
                    # A grounding-suppressed completion is classified by its
                    # owner; it is not an empty provider response.
                    if not has_visible_answer_text(leading):
                        if not gate.suppressed:
                            raise LLMProviderError("provider returned no answer text")
                        tail = ""
                    else:
                        tail, leading = leading, ""
                        visible = True
                        LOGGER.info(
                            "First answer text: provider=%s elapsed=%.3fs",
                            target.role,
                            time.monotonic() - started,
                        )
                if tail:
                    yield AnswerDelta(tail)
                LOGGER.info(
                    "Generation stream completed: provider=%s elapsed=%.3fs",
                    target.role,
                    time.monotonic() - started,
                )
                yield GeneratedText(gate.text.strip())
                return
            except (LLMProviderError, TimeoutError) as error:
                LOGGER.warning(
                    "Generation stream failed: provider=%s reason=%s elapsed=%.3fs partial=%s",
                    target.role,
                    failure_reason(error),
                    time.monotonic() - started,
                    visible,
                )
                if visible or index == len(self.targets) - 1:
                    if isinstance(error, LLMInputBudgetError):
                        raise
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
