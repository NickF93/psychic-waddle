# Backend Configuration

## Purpose

Provider configuration selects exactly one model backend behind the
`LLMProvider` contract. It does not perform retrieval, answer policy,
generation orchestration, question collection, or knowledge-base access.

Application code must build providers through the configuration layer. It must
not switch directly on concrete provider classes.

## Environment Variables

All names are explicit. There are no aliases, legacy names, or fallback
defaults.

| Name | Required | Description |
| --- | --- | --- |
| `LLM_BACKEND` | Yes | One of `ollama`, `llama-cpp`, `openai-compatible`. |
| `LLM_BASE_URL` | Yes | API root URL. Providers append only endpoint names. |
| `CHAT_MODEL` | Yes | Chat model configured for callers that build `ChatRequest`. |
| `EMBEDDING_MODEL` | Yes | Embedding model configured for callers that build `EmbeddingRequest`. |
| `LLM_API_KEY` | No | Optional bearer token. If blank or unset, no auth header is sent. |

`LLM_BASE_URL` must include the provider API root:

```env
LLM_BACKEND=ollama
LLM_BASE_URL=http://localhost:11434/api
CHAT_MODEL=llama3.2
EMBEDDING_MODEL=nomic-embed-text
```

```env
LLM_BACKEND=llama-cpp
LLM_BASE_URL=http://localhost:8080/v1
CHAT_MODEL=local-chat
EMBEDDING_MODEL=local-embedding
```

```env
LLM_BACKEND=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
LLM_API_KEY=replace-me
```

## Provider Routes

Concrete providers own backend-specific routes and payloads.

| Backend | Chat route | Embedding route |
| --- | --- | --- |
| `ollama` | `POST {LLM_BASE_URL}/chat` | `POST {LLM_BASE_URL}/embed` |
| `llama-cpp` | `POST {LLM_BASE_URL}/chat/completions` | `POST {LLM_BASE_URL}/embeddings` |
| `openai-compatible` | `POST {LLM_BASE_URL}/chat/completions` | `POST {LLM_BASE_URL}/embeddings` |

Ollama uses the native `/embed` route. The deprecated `/embeddings` route is
not used.

`ChatRequest.model` and `EmbeddingRequest.model` remain authoritative for
provider calls. The configured `CHAT_MODEL` and `EMBEDDING_MODEL` values are
stored for the future application layer that creates those requests.

## Error Translation

Providers translate backend failures into the provider-neutral error taxonomy:

- `LLMProviderConfigurationError`: invalid concrete provider settings.
- `LLMProviderRequestError`: provider returned a non-2xx HTTP response.
- `LLMProviderTransportError`: HTTP transport, connection, or timeout failure.
- `LLMProviderResponseError`: malformed JSON or response data that cannot
  satisfy the provider contract.

Provider-specific HTTP payloads, response shapes, and backend error bodies must
not leak into public contract models.
