from __future__ import annotations

import asyncio
from pathlib import Path

from intent_catalog_helpers import tracked_intent_catalog
from portfolio_rag_assistant.intent import SemanticIntentResolver
from portfolio_rag_assistant.provider import EmbeddingRequest, EmbeddingResponse

SEMANTIC_RESOLVER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "portfolio_rag_assistant"
    / "intent"
    / "semantic.py"
)


def test_semantic_resolver_embeds_catalog_anchors_not_trigger_words() -> None:
    catalog = tracked_intent_catalog()
    provider = FakeEmbeddingProvider(
        _anchor_embeddings_for_intent("professional_overview")
    )
    resolver = SemanticIntentResolver(
        catalog=catalog,
        provider=provider,
        embedding_model="nomic-embed-text",
    )

    resolution = asyncio.run(
        resolver.resolve(
            question="How would you summarize Niccolo for a recruiter?",
            question_embedding=(1.0, 0.0),
        )
    )

    assert provider.requests == (
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=_semantic_anchor_questions(),
        ),
    )
    assert "How would you summarize Niccolo for a recruiter?" not in str(
        provider.requests
    )
    assert resolution.required_intents == ()
    assert tuple(
        intent.identifier for intent in resolution.candidate_intents
    ) == ("professional_overview",)


def test_semantic_resolver_does_not_duplicate_lexical_required_intents() -> None:
    catalog = tracked_intent_catalog()
    provider = FakeEmbeddingProvider(_anchor_embeddings_for_intent("workplace"))
    resolver = SemanticIntentResolver(
        catalog=catalog,
        provider=provider,
        embedding_model="nomic-embed-text",
    )

    resolution = asyncio.run(
        resolver.resolve(
            question="Where did Niccolo work?",
            question_embedding=(1.0, 0.0),
        )
    )

    assert tuple(
        intent.identifier for intent in resolution.required_intents
    ) == ("workplace",)
    assert resolution.candidate_intents == ()
    assert tuple(
        intent.identifier for intent in resolution.retrieval_intents
    ) == ("workplace",)


def test_semantic_resolver_reuses_cached_anchor_embeddings() -> None:
    catalog = tracked_intent_catalog()
    provider = FakeEmbeddingProvider(_anchor_embeddings_for_intent("skills"))
    resolver = SemanticIntentResolver(
        catalog=catalog,
        provider=provider,
        embedding_model="nomic-embed-text",
    )

    asyncio.run(
        resolver.resolve(
            question="Which technical strengths would he bring?",
            question_embedding=(1.0, 0.0),
        )
    )
    asyncio.run(
        resolver.resolve(
            question="Which engineering abilities are strongest?",
            question_embedding=(1.0, 0.0),
        )
    )

    assert len(provider.requests) == 1


def test_semantic_resolver_has_no_intent_specific_branches() -> None:
    source = SEMANTIC_RESOLVER_SOURCE.read_text(encoding="utf-8")

    assert "if intent ==" not in source
    assert "if intent !=" not in source
    for profile in tracked_intent_catalog().profiles:
        assert f'"{profile.intent.identifier}"' not in source
        assert f"'{profile.intent.identifier}'" not in source


def _semantic_anchor_questions() -> tuple[str, ...]:
    return tuple(
        question
        for profile in tracked_intent_catalog().profiles
        for question in profile.semantic_example_questions
    )


def _anchor_embeddings_for_intent(
    intent_identifier: str,
) -> tuple[tuple[float, ...], ...]:
    return tuple(
        (1.0, 0.0) if profile.intent.identifier == intent_identifier else (-1.0, 0.0)
        for profile in tracked_intent_catalog().profiles
        for _question in profile.semantic_example_questions
    )


class FakeEmbeddingProvider:
    def __init__(self, embeddings: tuple[tuple[float, ...], ...]) -> None:
        self._embeddings = embeddings
        self.requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests = (*self.requests, request)
        return EmbeddingResponse(model=request.model, embeddings=self._embeddings)
