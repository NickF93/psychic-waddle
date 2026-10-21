"""Public chat orchestration service."""

from __future__ import annotations

import logging
import asyncio
import json
import math
import time
from contextlib import aclosing

from portfolio_rag_assistant.answer.contract import (
    AnswerDelta,
    AnswerGenerationResponse,
    GenerationStatus,
)

from portfolio_rag_assistant.answer import (
    AnswerGenerationError,
    AnswerGenerationRequest,
    AnswerGenerator,
)
from portfolio_rag_assistant.api.schemas import (
    ChatNoticeBody,
    ChatRequestBody,
    ChatResponseBody,
    ChatSourceBody,
)
from portfolio_rag_assistant.config import RetrievalSettings
from portfolio_rag_assistant.policy import (
    AnswerPolicy,
    AnswerPolicyError,
    AnswerPolicyRequest,
    NOT_ANSWERABLE,
)
from portfolio_rag_assistant.questions import (
    QuestionCollectionError,
    QuestionCollectionRequest,
    QuestionCollector,
)
from portfolio_rag_assistant.retrieval import (
    RetrievalError,
    RetrievalRequest,
    Retriever,
)

LOGGER = logging.getLogger(__name__)


class ChatServiceError(RuntimeError):
    """Raised when the public chat service cannot produce a safe response."""


class PublicChatService:
    """Orchestrate authorities for one public chat request."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        answer_policy: AnswerPolicy,
        answer_generator: AnswerGenerator,
        question_collector: QuestionCollector,
        retrieval_settings: RetrievalSettings,
        request_timeout: float = 240.0,
    ) -> None:
        if not isinstance(retriever, Retriever):
            raise ChatServiceError("retriever must satisfy Retriever")
        if not isinstance(answer_policy, AnswerPolicy):
            raise ChatServiceError("answer_policy must satisfy AnswerPolicy")
        if not isinstance(answer_generator, AnswerGenerator):
            raise ChatServiceError("answer_generator must satisfy AnswerGenerator")
        if not isinstance(question_collector, QuestionCollector):
            raise ChatServiceError("question_collector must satisfy QuestionCollector")
        if not isinstance(retrieval_settings, RetrievalSettings):
            raise ChatServiceError("retrieval_settings must be RetrievalSettings")
        self._retriever = retriever
        self._answer_policy = answer_policy
        self._answer_generator = answer_generator
        self._question_collector = question_collector
        self._retrieval_settings = retrieval_settings
        if (
            isinstance(request_timeout, bool)
            or not math.isfinite(request_timeout)
            or request_timeout <= 0
        ):
            raise ChatServiceError("request timeout must be finite and positive")
        self._request_timeout = request_timeout

    async def answer(self, request: ChatRequestBody) -> ChatResponseBody:
        """Return a public-safe response for one validated chat request."""
        started = time.monotonic()
        try:
            async with asyncio.timeout(self._request_timeout):
                prepared = await self._prepare(request)
                answer = await self._answer_generator.generate(prepared)
                return await self._public_response(request, answer)
        except (
            AnswerGenerationError,
            AnswerPolicyError,
            RetrievalError,
            ValueError,
            TimeoutError,
        ) as error:
            raise ChatServiceError("chat service failed") from error
        finally:
            LOGGER.info(
                "Chat request finished: elapsed=%.3fs", time.monotonic() - started
            )

    async def stream_answer(self, request: ChatRequestBody):
        """API-owned SSE adaptation of local policy and generation events."""
        started = time.monotonic()
        completed = False
        try:
            async with asyncio.timeout(self._request_timeout):
                yield _event("status", {"phase": "retrieving"})
                prepared = await self._prepare(request)
                stream_method = getattr(self._answer_generator, "stream", None)
                if not callable(stream_method):
                    raise ChatServiceError("streaming is not configured")
                async with aclosing(stream_method(prepared)) as stream:
                    async for item in stream:
                        if isinstance(item, GenerationStatus):
                            yield _event(
                                "status", {"phase": "generating", "provider": item.role}
                            )
                        elif isinstance(item, AnswerDelta):
                            yield _event("delta", {"text": item.text})
                        elif isinstance(item, AnswerGenerationResponse):
                            body = await self._public_response(request, item)
                            completed = True
                            yield _event("complete", body.model_dump(mode="json"))
                            return
                raise ChatServiceError("generation ended without completion")
        except asyncio.CancelledError:
            LOGGER.info(
                "Chat stream cancelled: elapsed=%.3fs", time.monotonic() - started
            )
            raise
        except (
            AnswerGenerationError,
            AnswerPolicyError,
            RetrievalError,
            ValueError,
            TimeoutError,
            ChatServiceError,
        ) as error:
            LOGGER.warning(
                "Chat stream failed: reason=%s elapsed=%.3fs",
                type(error).__name__,
                time.monotonic() - started,
            )
            yield _event(
                "error",
                {
                    "code": "service_unavailable",
                    "message": "The answer could not be completed. Please retry.",
                },
            )
        finally:
            LOGGER.info(
                "Chat stream finished: completed=%s elapsed=%.3fs",
                completed,
                time.monotonic() - started,
            )

    async def _prepare(self, request: ChatRequestBody) -> AnswerGenerationRequest:
        started = time.monotonic()
        retrieval_response = await self._retriever.retrieve(
            RetrievalRequest(
                question=request.question, top_k=self._retrieval_settings.top_k
            )
        )
        decision = self._answer_policy.decide(
            AnswerPolicyRequest(
                question=request.question,
                retrieved_context=retrieval_response.results,
                intent_resolution=retrieval_response.intent_resolution,
                min_score=self._retrieval_settings.min_score,
            )
        )
        LOGGER.info(
            "Local retrieval and evidence approval finished: elapsed=%.3fs",
            time.monotonic() - started,
        )
        return AnswerGenerationRequest(
            question=request.question, decision=decision, language=request.language
        )

    async def _public_response(self, request, answer_response) -> ChatResponseBody:
        notices = await self._collect_question_notice(
            request=request, status=answer_response.status
        )
        return ChatResponseBody(
            status=answer_response.status,
            answer=answer_response.answer_text,
            sources=tuple(
                ChatSourceBody(title=source.source_title, locator=source.source_locator)
                for source in answer_response.sources
            ),
            notices=notices,
        )

    async def _collect_question_notice(
        self,
        *,
        request: ChatRequestBody,
        status: str,
    ) -> tuple[ChatNoticeBody, ...]:
        if status != NOT_ANSWERABLE:
            return ()
        try:
            result = await self._question_collector.collect(
                QuestionCollectionRequest(raw_question_text=request.question)
            )
        except QuestionCollectionError:
            LOGGER.warning("question collection failed")
            return ()
        if not result.recorded:
            return ()
        return (ChatNoticeBody(code="question_recorded"),)


def _event(name: str, body: dict) -> dict[str, str]:
    return {"event": name, "data": json.dumps(body)}
