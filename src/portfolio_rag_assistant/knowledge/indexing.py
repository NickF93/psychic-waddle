"""Embedding indexing for approved knowledge chunks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from portfolio_rag_assistant.knowledge.store import (
    ChunkEmbeddingInput,
    KnowledgeStore,
    StoredChunk,
)
from portfolio_rag_assistant.provider import EmbeddingRequest, LLMProvider


class EmbeddingIndexingError(RuntimeError):
    """Raised when chunks cannot be indexed through the provider contract."""


@dataclass(frozen=True, slots=True)
class EmbeddingIndexResult:
    """Result of one embedding indexing run."""

    indexed_count: int


async def index_embeddings(
    *,
    store: KnowledgeStore,
    provider: LLMProvider,
    backend: str,
    model: str,
    batch_size: int = 32,
) -> EmbeddingIndexResult:
    """Generate embeddings for public chunks missing the selected backend/model."""

    if batch_size <= 0:
        raise EmbeddingIndexingError("batch_size must be positive")

    chunks = store.list_public_chunks_missing_embedding(backend, model)
    indexed_count = 0

    for chunk_batch in _batched(chunks, batch_size):
        response = await provider.embed(
            EmbeddingRequest(
                model=model,
                inputs=tuple(chunk.chunk_text for chunk in chunk_batch),
            )
        )
        if len(response.embeddings) != len(chunk_batch):
            raise EmbeddingIndexingError("provider returned the wrong embedding count")
        store.upsert_chunk_embeddings(
            backend=backend,
            model=model,
            embeddings=tuple(
                ChunkEmbeddingInput(chunk_id=chunk.id, embedding=embedding)
                for chunk, embedding in zip(chunk_batch, response.embeddings, strict=True)
            ),
        )
        indexed_count += len(chunk_batch)

    return EmbeddingIndexResult(indexed_count=indexed_count)


def _batched(
    chunks: Sequence[StoredChunk],
    batch_size: int,
) -> tuple[tuple[StoredChunk, ...], ...]:
    return tuple(
        tuple(chunks[index : index + batch_size])
        for index in range(0, len(chunks), batch_size)
    )
