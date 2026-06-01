from __future__ import annotations

import asyncio

import pytest

from portfolio_rag_assistant.answer import (
    AnswerGenerationRequest,
    AnswerGenerationResponse,
    AnswerSourceReference,
)
from portfolio_rag_assistant.api import (
    ChatRequestBody,
    ChatSourceBody,
    ChatServiceError,
    PublicChatService,
)
from portfolio_rag_assistant.config import RetrievalSettings
from portfolio_rag_assistant.policy import (
    ANSWERABLE,
    NEEDS_CLARIFICATION,
    NOT_ANSWERABLE,
    AnswerPolicyDecision,
    AnswerPolicyRequest,
    DeterministicAnswerPolicy,
)
from portfolio_rag_assistant.questions import (
    QuestionCollectionError,
    QuestionCollectionRequest,
    QuestionCollectionResult,
)
from portfolio_rag_assistant.retrieval import (
    RetrievedContext,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalScore,
    RetrievalStoreError,
)


def test_chat_service_orchestrates_answerable_flow() -> None:
    events: list[str] = []
    context = _context()
    decision = AnswerPolicyDecision(
        status=ANSWERABLE,
        reason="sufficient_source_backed_context",
        approved_context=(context,),
    )
    retriever = FakeRetriever(
        RetrievalResponse(
            question="Where did Niccolo work?",
            results=(context,),
        ),
        events,
    )
    policy = FakePolicy(decision, events)
    generator = FakeGenerator(
        AnswerGenerationResponse(
            status=ANSWERABLE,
            answer_text="Niccolo worked at NAIS s.r.l.\n\nSources: CV.",
            sources=(
                AnswerSourceReference(
                    source_title="Niccolo Ferrari CV",
                    source_uri="cv://niccolo/main",
                    source_locator="Experience section",
                ),
            ),
        ),
        events,
    )
    service = _service(retriever=retriever, policy=policy, generator=generator)

    response = _run(
        service.answer(
            ChatRequestBody(question="Where did Niccolo work?", language="en")
        )
    )

    assert events == ["retrieve", "decide", "generate"]
    assert retriever.requests == (
        RetrievalRequest(question="Where did Niccolo work?", top_k=3),
    )
    assert policy.requests == (
        AnswerPolicyRequest(
            question="Where did Niccolo work?",
            retrieved_context=(context,),
            min_score=0.25,
        ),
    )
    assert generator.requests == (
        AnswerGenerationRequest(
            question="Where did Niccolo work?",
            decision=decision,
            language="en",
        ),
    )
    assert response.model_dump(mode="json", exclude_none=True) == {
        "status": "answerable",
        "answer": "Niccolo worked at NAIS s.r.l.\n\nSources: CV.",
        "sources": [
            {
                "title": "Niccolo Ferrari CV",
                "locator": "Experience section",
            }
        ],
        "notices": [],
    }
    assert "cv://niccolo/main" not in str(response.model_dump(mode="json"))


def test_chat_service_returns_not_answerable_generator_response() -> None:
    collector = FakeQuestionCollector(recorded=True)
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(question="Private phone?", results=()),
            [],
        ),
        policy=FakePolicy(
            AnswerPolicyDecision(
                status=NOT_ANSWERABLE,
                reason="no_retrieved_context",
            ),
            [],
        ),
        generator=FakeGenerator(
            AnswerGenerationResponse(
                status=NOT_ANSWERABLE,
                answer_text="I do not have verified public context.",
            ),
            [],
        ),
        question_collector=collector,
    )

    response = _run(
        service.answer(ChatRequestBody(question="Private phone?", language="en"))
    )

    assert response.status == NOT_ANSWERABLE
    assert response.answer == "I do not have verified public context."
    assert response.sources == ()
    assert response.model_dump(mode="json")["notices"] == [
        {"code": "question_recorded"}
    ]
    assert collector.requests == (
        QuestionCollectionRequest(raw_question_text="Private phone?"),
    )


def test_chat_service_returns_clarification_generator_response() -> None:
    collector = FakeQuestionCollector(recorded=True)
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(question="Tell me about Niccolo", results=(_context(),)),
            [],
        ),
        policy=FakePolicy(
            AnswerPolicyDecision(
                status=NEEDS_CLARIFICATION,
                reason="ambiguous_question",
            ),
            [],
        ),
        generator=FakeGenerator(
            AnswerGenerationResponse(
                status=NEEDS_CLARIFICATION,
                answer_text="Please ask a more specific question.",
            ),
            [],
        ),
        question_collector=collector,
    )

    response = _run(
        service.answer(
            ChatRequestBody(question="Tell me about Niccolo", language="en")
        )
    )

    assert response.status == NEEDS_CLARIFICATION
    assert response.answer == "Please ask a more specific question."
    assert response.sources == ()
    assert response.notices == ()
    assert collector.requests == ()


def test_chat_service_does_not_collect_answerable_questions() -> None:
    collector = FakeQuestionCollector(recorded=True)
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(question="Where did Niccolo work?", results=(_context(),)),
            [],
        ),
        policy=FakePolicy(
            AnswerPolicyDecision(
                status=ANSWERABLE,
                reason="sufficient_source_backed_context",
                approved_context=(_context(),),
            ),
            [],
        ),
        generator=FakeGenerator(
            AnswerGenerationResponse(
                status=ANSWERABLE,
                answer_text="Niccolo worked at NAIS s.r.l.",
                sources=(
                    AnswerSourceReference(
                        source_title="Niccolo Ferrari CV",
                        source_uri="cv://niccolo/main",
                        source_locator="Experience section",
                    ),
                ),
            ),
            [],
        ),
        question_collector=collector,
    )

    response = _run(
        service.answer(
            ChatRequestBody(question="Where did Niccolo work?", language="en")
        )
    )

    assert response.status == ANSWERABLE
    assert response.notices == ()
    assert collector.requests == ()


def test_chat_service_collects_real_policy_not_answerable_question() -> None:
    collector = FakeQuestionCollector(recorded=True)
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(
                question="What is Niccolo favorite pizza topping?",
                results=(_context(),),
            ),
            [],
        ),
        policy=DeterministicAnswerPolicy(),
        generator=DecisionEchoGenerator(),
        question_collector=collector,
    )

    response = _run(
        service.answer(
            ChatRequestBody(
                question="What is Niccolo favorite pizza topping?",
                language="en",
            )
        )
    )

    assert response.status == NOT_ANSWERABLE
    assert response.sources == ()
    assert response.model_dump(mode="json")["notices"] == [
        {"code": "question_recorded"}
    ]
    assert collector.requests == (
        QuestionCollectionRequest(
            raw_question_text="What is Niccolo favorite pizza topping?"
        ),
    )


def test_chat_service_does_not_collect_real_policy_answerable_question() -> None:
    collector = FakeQuestionCollector(recorded=True)
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(question="Where did Niccolo work?", results=(_context(),)),
            [],
        ),
        policy=DeterministicAnswerPolicy(),
        generator=DecisionEchoGenerator(),
        question_collector=collector,
    )

    response = _run(
        service.answer(
            ChatRequestBody(question="Where did Niccolo work?", language="en")
        )
    )

    assert response.status == ANSWERABLE
    assert response.sources == (
        ChatSourceBody(
            title="Niccolo Ferrari CV",
            locator="Experience section",
        ),
    )
    assert response.notices == ()
    assert collector.requests == ()


def test_chat_service_ignores_question_collection_failures() -> None:
    service = _service(
        retriever=FakeRetriever(
            RetrievalResponse(question="Private phone?", results=()),
            [],
        ),
        policy=FakePolicy(
            AnswerPolicyDecision(
                status=NOT_ANSWERABLE,
                reason="no_retrieved_context",
            ),
            [],
        ),
        generator=FakeGenerator(
            AnswerGenerationResponse(
                status=NOT_ANSWERABLE,
                answer_text="I do not have verified public context.",
            ),
            [],
        ),
        question_collector=FailingQuestionCollector(),
    )

    response = _run(
        service.answer(ChatRequestBody(question="Private phone?", language="en"))
    )

    assert response.status == NOT_ANSWERABLE
    assert response.notices == ()


def test_chat_service_sanitizes_internal_errors() -> None:
    service = _service(
        retriever=FailingRetriever(),
        policy=FakePolicy(
            AnswerPolicyDecision(status=NOT_ANSWERABLE, reason="unused"),
            [],
        ),
        generator=FakeGenerator(
            AnswerGenerationResponse(status=NOT_ANSWERABLE, answer_text="unused"),
            [],
        ),
    )

    with pytest.raises(ChatServiceError) as error:
        _run(
            service.answer(
                ChatRequestBody(question="Where did Niccolo work?", language="en")
            )
        )

    assert str(error.value) == "chat service failed"
    assert "database password" not in str(error.value)


def _service(
    *,
    retriever: object,
    policy: object,
    generator: object,
    question_collector: object | None = None,
) -> PublicChatService:
    return PublicChatService(
        retriever=retriever,  # type: ignore[arg-type]
        answer_policy=policy,  # type: ignore[arg-type]
        answer_generator=generator,  # type: ignore[arg-type]
        question_collector=question_collector or FakeQuestionCollector(recorded=False),
        retrieval_settings=RetrievalSettings(top_k=3, min_score=0.25),
    )


def _context() -> RetrievedContext:
    return RetrievedContext(
        chunk_id=1,
        chunk_text="experience: Niccolo worked at NAIS s.r.l.",
        category="experience",
        source_uri="cv://niccolo/main",
        source_title="Niccolo Ferrari CV",
        source_locator="Experience section",
        score=RetrievalScore(combined_score=0.91),
    )


def _run(awaitable):
    return asyncio.run(awaitable)


class FakeRetriever:
    def __init__(
        self,
        response: RetrievalResponse,
        events: list[str],
    ) -> None:
        self._response = response
        self._events = events
        self.requests: tuple[RetrievalRequest, ...] = ()

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self._events.append("retrieve")
        self.requests = (*self.requests, request)
        return self._response


class FailingRetriever:
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        raise RetrievalStoreError("database password leaked")


class FakeQuestionCollector:
    def __init__(self, *, recorded: bool) -> None:
        self._recorded = recorded
        self.requests: tuple[QuestionCollectionRequest, ...] = ()

    async def collect(
        self,
        request: QuestionCollectionRequest,
    ) -> QuestionCollectionResult:
        self.requests = (*self.requests, request)
        if self._recorded:
            return QuestionCollectionResult(recorded=True, event_id=1)
        return QuestionCollectionResult(recorded=False)


class FailingQuestionCollector:
    async def collect(
        self,
        request: QuestionCollectionRequest,
    ) -> QuestionCollectionResult:
        raise QuestionCollectionError("database password leaked")


class FakePolicy:
    def __init__(
        self,
        decision: AnswerPolicyDecision,
        events: list[str],
    ) -> None:
        self._decision = decision
        self._events = events
        self.requests: tuple[AnswerPolicyRequest, ...] = ()

    def decide(self, request: AnswerPolicyRequest) -> AnswerPolicyDecision:
        self._events.append("decide")
        self.requests = (*self.requests, request)
        return self._decision


class FakeGenerator:
    def __init__(
        self,
        response: AnswerGenerationResponse,
        events: list[str],
    ) -> None:
        self._response = response
        self._events = events
        self.requests: tuple[AnswerGenerationRequest, ...] = ()

    async def generate(
        self,
        request: AnswerGenerationRequest,
    ) -> AnswerGenerationResponse:
        self._events.append("generate")
        self.requests = (*self.requests, request)
        return self._response


class DecisionEchoGenerator:
    async def generate(
        self,
        request: AnswerGenerationRequest,
    ) -> AnswerGenerationResponse:
        sources = tuple(
            AnswerSourceReference(
                source_title=context.source_title,
                source_uri=context.source_uri,
                source_locator=context.source_locator,
            )
            for context in request.decision.approved_context
        )
        return AnswerGenerationResponse(
            status=request.decision.status,
            answer_text=f"{request.decision.status}: {request.decision.reason}",
            sources=sources,
        )
