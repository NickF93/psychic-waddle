from __future__ import annotations

import asyncio
import hashlib

import pytest

from portfolio_rag_assistant.knowledge import (
    ChunkEmbeddingInput,
    EmbeddingIndexingError,
    StoredChunk,
    index_embeddings,
)
from portfolio_rag_assistant.provider import EmbeddingRequest, EmbeddingResponse


def test_index_embeddings_stores_vectors_for_missing_chunks() -> None:
    store = FakeEmbeddingStore((StoredChunk(id=1, chunk_text="experience: NAIS"),))
    provider = FakeEmbeddingProvider()

    result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )

    assert result.indexed_count == 1
    assert provider.requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("experience: NAIS",)),
    )
    assert store.embeddings == {
        (1, "ollama", "nomic-embed-text"): (
            _chunk_text_hash("experience: NAIS"),
            (16.0, 0.0),
        ),
    }


def test_index_embeddings_skips_unchanged_backend_model_pairs() -> None:
    store = FakeEmbeddingStore((StoredChunk(id=1, chunk_text="experience: NAIS"),))
    provider = FakeEmbeddingProvider()

    first_result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )
    second_result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )

    assert first_result.indexed_count == 1
    assert second_result.indexed_count == 0
    assert len(provider.requests) == 1
    assert len(store.embeddings) == 1


def test_index_embeddings_refreshes_changed_chunk_text() -> None:
    store = FakeEmbeddingStore((StoredChunk(id=1, chunk_text="experience: NAIS"),))
    provider = FakeEmbeddingProvider()

    first_result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )
    store.chunks = (StoredChunk(id=1, chunk_text="experience: NAIS in Bologna"),)
    second_result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )

    assert first_result.indexed_count == 1
    assert second_result.indexed_count == 1
    assert provider.requests == (
        EmbeddingRequest(model="nomic-embed-text", inputs=("experience: NAIS",)),
        EmbeddingRequest(
            model="nomic-embed-text",
            inputs=("experience: NAIS in Bologna",),
        ),
    )
    assert store.embeddings[(1, "ollama", "nomic-embed-text")] == (
        _chunk_text_hash("experience: NAIS in Bologna"),
        (27.0, 0.0),
    )


def test_index_embeddings_keeps_distinct_backend_model_rows() -> None:
    store = FakeEmbeddingStore((StoredChunk(id=1, chunk_text="experience: NAIS"),))
    provider = FakeEmbeddingProvider()

    _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )
    _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="openai-compatible",
            model="text-embedding-3-small",
        )
    )

    assert set(store.embeddings) == {
        (1, "ollama", "nomic-embed-text"),
        (1, "openai-compatible", "text-embedding-3-small"),
    }


def test_index_embeddings_refreshes_only_selected_backend_model() -> None:
    store = FakeEmbeddingStore((StoredChunk(id=1, chunk_text="experience: NAIS"),))
    provider = FakeEmbeddingProvider()

    _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )
    _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="openai-compatible",
            model="text-embedding-3-small",
        )
    )

    store.chunks = (StoredChunk(id=1, chunk_text="experience: NAIS in Bologna"),)
    result = _run(
        index_embeddings(
            store=store,
            provider=provider,
            backend="ollama",
            model="nomic-embed-text",
        )
    )

    assert result.indexed_count == 1
    assert store.embeddings[(1, "ollama", "nomic-embed-text")] == (
        _chunk_text_hash("experience: NAIS in Bologna"),
        (27.0, 0.0),
    )
    assert store.embeddings[(1, "openai-compatible", "text-embedding-3-small")] == (
        _chunk_text_hash("experience: NAIS"),
        (16.0, 0.0),
    )


def test_index_embeddings_rejects_invalid_batch_size() -> None:
    with pytest.raises(EmbeddingIndexingError, match="batch_size"):
        _run(
            index_embeddings(
                store=FakeEmbeddingStore(()),
                provider=FakeEmbeddingProvider(),
                backend="ollama",
                model="nomic-embed-text",
                batch_size=0,
            )
        )


def _run(awaitable):
    return asyncio.run(awaitable)


def _chunk_text_hash(chunk_text: str) -> str:
    return hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()


class FakeEmbeddingStore:
    def __init__(self, chunks: tuple[StoredChunk, ...]) -> None:
        self.chunks = chunks
        self.embeddings: dict[tuple[int, str, str], tuple[str, tuple[float, ...]]] = {}

    def list_public_chunks_requiring_embedding(
        self,
        backend: str,
        model: str,
    ) -> tuple[StoredChunk, ...]:
        return tuple(
            chunk
            for chunk in self.chunks
            if self.embeddings.get((chunk.id, backend, model), (None, ()))[0]
            != _chunk_text_hash(chunk.chunk_text)
        )

    def upsert_chunk_embeddings(
        self,
        *,
        backend: str,
        model: str,
        embeddings: tuple[ChunkEmbeddingInput, ...],
    ) -> None:
        for embedding in embeddings:
            self.embeddings[(embedding.chunk_id, backend, model)] = (
                embedding.chunk_text_hash,
                embedding.embedding,
            )


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.requests: tuple[EmbeddingRequest, ...] = ()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests = (*self.requests, request)
        return EmbeddingResponse(
            model=request.model,
            embeddings=tuple(
                (float(len(item)), float(index))
                for index, item in enumerate(request.inputs)
            ),
        )
