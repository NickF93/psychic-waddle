"""Public chat orchestration service."""

from __future__ import annotations

import logging

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

    async def answer(self, request: ChatRequestBody) -> ChatResponseBody:
        """Return a public-safe response for one validated chat request."""

        try:
            retrieval_response = await self._retriever.retrieve(
                RetrievalRequest(
                    question=request.question,
                    top_k=self._retrieval_settings.top_k,
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
            answer_response = await self._answer_generator.generate(
                AnswerGenerationRequest(
                    question=request.question,
                    decision=decision,
                    language=request.language,
                )
            )
            notices = await self._collect_question_notice(
                request=request,
                status=answer_response.status,
            )
            return ChatResponseBody(
                status=answer_response.status,
                answer=answer_response.answer_text,
                sources=tuple(
                    ChatSourceBody(
                        title=source.source_title,
                        locator=source.source_locator,
                    )
                    for source in answer_response.sources
                ),
                notices=notices,
            )
        except (
            AnswerGenerationError,
            AnswerPolicyError,
            RetrievalError,
            ValueError,
        ) as error:
            raise ChatServiceError("chat service failed") from error

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
