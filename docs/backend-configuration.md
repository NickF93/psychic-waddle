# Backend Configuration

## Purpose

Provider configuration selects explicit model capabilities behind
provider-neutral contracts. Chat and embeddings are configured separately
because a deployment may serve them from the same endpoint or from different
systems.

Provider configuration does not perform retrieval, answer policy, generation
orchestration, question collection, or knowledge-base access.

Application code must build providers through the configuration layer. It must
not switch directly on concrete provider classes.

## Environment Variables

All names are explicit. There are no aliases, legacy names, or fallback
defaults.

| Name | Required | Description |
| --- | --- | --- |
| `CHAT_BACKEND` | Yes | One of `ollama`, `llama-cpp`, `openai-compatible`. |
| `CHAT_BASE_URL` | Yes | API root URL for chat requests. |
| `CHAT_MODEL` | Yes | Chat model used by answer generation. |
| `CHAT_API_KEY` | No | Optional bearer token for chat requests. |
| `EMBEDDING_BACKEND` | Yes | One of `ollama`, `llama-cpp`, `openai-compatible`. |
| `EMBEDDING_BASE_URL` | Yes | API root URL for embedding requests. |
| `EMBEDDING_MODEL` | Yes | Embedding model used for indexing and retrieval. |
| `EMBEDDING_API_KEY` | No | Optional bearer token for embedding requests. |

Use one provider for both capabilities by setting both base URLs to the same
API root:

```env
CHAT_BACKEND=openai-compatible
CHAT_BASE_URL=https://api.example.com/v1
CHAT_MODEL=chat-model
CHAT_API_KEY=replace-me

EMBEDDING_BACKEND=openai-compatible
EMBEDDING_BASE_URL=https://api.example.com/v1
EMBEDDING_MODEL=embedding-model
EMBEDDING_API_KEY=replace-me
```

Use mixed providers by setting capability-specific values:

```env
CHAT_BACKEND=openai-compatible
CHAT_BASE_URL=https://api.example.com/v1
CHAT_MODEL=external-chat-model
CHAT_API_KEY=replace-me

EMBEDDING_BACKEND=ollama
EMBEDDING_BASE_URL=http://localhost:11434/api
EMBEDDING_MODEL=nomic-embed-text
```

## Provider Routes

Concrete providers own backend-specific routes and payloads.

| Backend | Chat route | Embedding route |
| --- | --- | --- |
| `ollama` | `POST {CHAT_BASE_URL}/chat` | `POST {EMBEDDING_BASE_URL}/embed` |
| `llama-cpp` | `POST {CHAT_BASE_URL}/chat/completions` | `POST {EMBEDDING_BASE_URL}/embeddings` |
| `openai-compatible` | `POST {CHAT_BASE_URL}/chat/completions` | `POST {EMBEDDING_BASE_URL}/embeddings` |

Ollama uses the native `/embed` route. The deprecated `/embeddings` route is
not used.

`ChatRequest.model` and `EmbeddingRequest.model` remain authoritative for
provider calls.

## Error Translation

Providers translate backend failures into the provider-neutral error taxonomy:

- `LLMProviderConfigurationError`: invalid concrete provider settings.
- `LLMProviderRequestError`: provider returned a non-2xx HTTP response.
- `LLMProviderTransportError`: HTTP transport, connection, or timeout failure.
- `LLMProviderResponseError`: malformed JSON or response data that cannot
  satisfy the provider contract.

Provider-specific HTTP payloads, response shapes, and backend error bodies must
not leak into public contract models.
