# Provider Contract

## Purpose

The provider contract defines the only model I/O surface used by the
application. It supports chat completion and embedding calls without exposing
Ollama, llama.cpp, OpenAI-compatible payloads, authentication details, HTTP
routes, or backend-specific response shapes.

Provider implementations belong behind these contracts. Application authorities
must depend on the narrow capability they need, not on a concrete backend.

## Interface

`ChatProvider` owns chat model I/O only:

```python
class ChatProvider(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResponse: ...
```

`EmbeddingProvider` owns embedding model I/O only:

```python
class EmbeddingProvider(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...
```

Both methods are async because real providers perform network I/O.

`chat()` receives a `ChatRequest` and returns exactly one assistant
`ChatResponse`. It must not retrieve knowledge, decide answerability, collect
questions, or add facts.

`embed()` receives an `EmbeddingRequest` and returns an `EmbeddingResponse` with
embeddings in the same order as the request inputs. It must not store vectors,
rank chunks, or mutate the knowledge base.

## Models

All models are provider-neutral frozen dataclasses.

- `ChatMessage`: `role` and `content`. Allowed roles are `system`, `user`, and
  `assistant`.
- `ChatRequest`: `model`, `messages`, optional `temperature`, and optional
  `max_tokens`.
- `ChatResponse`: `model`, assistant `message`, and optional `usage`.
- `EmbeddingRequest`: `model` and ordered text `inputs`.
- `EmbeddingResponse`: `model` and ordered `embeddings`.
- `TokenUsage`: optional `input_tokens`, `output_tokens`, and `total_tokens`.

Invalid local model construction raises `ValueError`. Provider-owned failures
raise provider errors.

## Errors

All provider-owned failures inherit from `LLMProviderError`.

- `LLMProviderConfigurationError`: invalid concrete provider configuration.
- `LLMProviderRequestError`: provider rejects a valid contract request.
- `LLMProviderTransportError`: provider transport fails.
- `LLMProviderResponseError`: provider response cannot satisfy the contract.

Provider implementations may translate backend-specific failures into these
errors, but they must not leak backend payloads as public contract types.

## Boundaries

Provider code may own:

- Backend HTTP payload construction.
- Backend authentication.
- Backend route selection.
- Backend response parsing.
- Translation into provider-neutral models and errors.

Provider code must not own:

- Retrieval, ranking, or knowledge storage.
- Answerability policy.
- Final answer wording rules beyond returning raw model output.
- Anonymous question collection.
- Runtime provider selection outside the configuration layer.

## Sprint 1.1 Non-Goals

This sprint does not implement Ollama, llama.cpp, OpenAI-compatible clients,
configuration loading, FastAPI endpoints, database access, retrieval, answer
policy, answer generation, or ingestion.
