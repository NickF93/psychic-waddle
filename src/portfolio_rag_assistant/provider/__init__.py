"""Provider-neutral LLM contract."""

from portfolio_rag_assistant.provider.contract import (
    ALLOWED_CHAT_ROLES,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingVector,
    LLMProvider,
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMProviderTransportError,
    TokenUsage,
)
from portfolio_rag_assistant.provider.llama_cpp import LlamaCppProvider
from portfolio_rag_assistant.provider.ollama import OllamaProvider
from portfolio_rag_assistant.provider.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "ALLOWED_CHAT_ROLES",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "EmbeddingVector",
    "LLMProvider",
    "LLMProviderConfigurationError",
    "LLMProviderError",
    "LLMProviderRequestError",
    "LLMProviderResponseError",
    "LLMProviderTransportError",
    "LlamaCppProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "TokenUsage",
]
