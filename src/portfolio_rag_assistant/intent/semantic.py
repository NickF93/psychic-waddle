"""Semantic intent resolution over reviewed catalog anchors."""

from __future__ import annotations

import math
from dataclasses import dataclass

from portfolio_rag_assistant.intent.profiles import (
    IntentCatalog,
    IntentResolution,
    QuestionIntent,
    QuestionIntentProfileError,
)
from portfolio_rag_assistant.provider import (
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingVector,
)


@dataclass(frozen=True, slots=True)
class SemanticIntentScore:
    """Best semantic score for one catalog-owned intent."""

    intent: QuestionIntent
    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.intent, QuestionIntent):
            raise QuestionIntentProfileError(
                "semantic intent scores must use catalog QuestionIntent values"
            )
        if not isinstance(self.score, float) or isinstance(self.score, bool):
            raise QuestionIntentProfileError("semantic intent score must be a float")
        if not -1.0 <= self.score <= 1.0:
            raise QuestionIntentProfileError(
                "semantic intent score must be between -1 and 1"
            )


@dataclass(frozen=True, slots=True)
class _SemanticAnchor:
    intent: QuestionIntent
    question: str
    embedding: EmbeddingVector


class SemanticIntentResolver:
    """Resolve lexical required intents plus semantic candidate intents."""

    def __init__(
        self,
        *,
        catalog: IntentCatalog,
        provider: EmbeddingProvider,
        embedding_model: str,
    ) -> None:
        if not isinstance(catalog, IntentCatalog):
            raise QuestionIntentProfileError("catalog must be IntentCatalog")
        self._catalog = catalog
        self._provider = provider
        self._embedding_model = _require_text(embedding_model, "embedding_model")
        self._anchors: tuple[_SemanticAnchor, ...] | None = None

    @property
    def catalog(self) -> IntentCatalog:
        """Return the reviewed catalog backing this resolver."""

        return self._catalog

    async def resolve(
        self,
        *,
        question: str,
        question_embedding: EmbeddingVector,
    ) -> IntentResolution:
        """Return required lexical intents and candidate semantic intents."""

        required_intents = self._catalog.detect_question_intents(question)
        required_identifiers = {intent.identifier for intent in required_intents}
        promoted_required_intents = list(required_intents)
        candidate_intents: list[QuestionIntent] = []
        for score in await self.score_semantic_intents(question_embedding):
            if score.intent.identifier in required_identifiers:
                continue
            profile = self._catalog.profile_for_intent(score.intent)
            if (
                profile.semantic_required_threshold is not None
                and score.score >= profile.semantic_required_threshold
            ):
                promoted_required_intents.append(score.intent)
                required_identifiers.add(score.intent.identifier)
                continue
            if score.score >= profile.semantic_candidate_threshold:
                candidate_intents.append(score.intent)
        return IntentResolution(
            required_intents=tuple(promoted_required_intents),
            candidate_intents=tuple(candidate_intents),
        )

    async def score_semantic_intents(
        self,
        question_embedding: EmbeddingVector,
    ) -> tuple[SemanticIntentScore, ...]:
        """Return best anchor-similarity score per intent in catalog order."""

        anchors = await self._semantic_anchors()
        scores: list[SemanticIntentScore] = []
        for profile in self._catalog.profiles:
            best_score: float | None = None
            for anchor in anchors:
                if anchor.intent != profile.intent:
                    continue
                score = _cosine_similarity(question_embedding, anchor.embedding)
                if best_score is None or score > best_score:
                    best_score = score
            if best_score is not None:
                scores.append(SemanticIntentScore(profile.intent, best_score))
        return tuple(scores)

    async def _semantic_anchors(self) -> tuple[_SemanticAnchor, ...]:
        if self._anchors is not None:
            return self._anchors

        anchor_specs = tuple(
            (profile.intent, question)
            for profile in self._catalog.profiles
            for question in profile.semantic_example_questions
        )
        response = await self._provider.embed(
            EmbeddingRequest(
                model=self._embedding_model,
                inputs=tuple(question for _intent, question in anchor_specs),
            )
        )
        if len(response.embeddings) != len(anchor_specs):
            raise QuestionIntentProfileError(
                "embedding provider returned the wrong semantic anchor count"
            )
        self._anchors = tuple(
            _SemanticAnchor(
                intent=intent,
                question=question,
                embedding=embedding,
            )
            for (intent, question), embedding in zip(
                anchor_specs,
                response.embeddings,
                strict=True,
            )
        )
        return self._anchors


def _cosine_similarity(
    left: EmbeddingVector,
    right: EmbeddingVector,
) -> float:
    if len(left) != len(right):
        raise QuestionIntentProfileError(
            "semantic embedding dimensions must match"
        )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    ) / (left_norm * right_norm)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuestionIntentProfileError(f"{field_name} must be set")
    return value.strip()
