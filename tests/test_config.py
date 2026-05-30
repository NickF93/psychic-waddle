from __future__ import annotations

import pytest

from portfolio_rag_assistant.config import (
    ProviderSettings,
    RetrievalSettings,
    build_llm_provider,
    load_provider_settings,
    load_retrieval_settings,
)
from portfolio_rag_assistant.provider import (
    LLMProviderConfigurationError,
    LlamaCppProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from portfolio_rag_assistant.retrieval import RetrievalConfigurationError


def test_load_provider_settings_reads_exact_env_names() -> None:
    settings = load_provider_settings(
        {
            "LLM_BACKEND": "ollama",
            "LLM_BASE_URL": " http://localhost:11434/api/ ",
            "CHAT_MODEL": " llama3.2 ",
            "EMBEDDING_MODEL": " nomic-embed-text ",
            "LLM_API_KEY": " local-secret ",
        }
    )

    assert settings == ProviderSettings(
        backend="ollama",
        base_url="http://localhost:11434/api",
        chat_model="llama3.2",
        embedding_model="nomic-embed-text",
        api_key="local-secret",
    )


def test_load_provider_settings_treats_blank_api_key_as_missing() -> None:
    settings = load_provider_settings(
        {
            "LLM_BACKEND": "llama-cpp",
            "LLM_BASE_URL": "http://localhost:8080/v1",
            "CHAT_MODEL": "local-chat",
            "EMBEDDING_MODEL": "local-embed",
            "LLM_API_KEY": " ",
        }
    )

    assert settings.api_key is None


@pytest.mark.parametrize(
    "missing_name",
    ("LLM_BACKEND", "LLM_BASE_URL", "CHAT_MODEL", "EMBEDDING_MODEL"),
)
def test_load_provider_settings_requires_named_values(missing_name: str) -> None:
    env = {
        "LLM_BACKEND": "openai-compatible",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "CHAT_MODEL": "chat-model",
        "EMBEDDING_MODEL": "embedding-model",
    }
    del env[missing_name]

    with pytest.raises(LLMProviderConfigurationError):
        load_provider_settings(env)


@pytest.mark.parametrize(
    "backend",
    ("ollama", "llama-cpp", "openai-compatible"),
)
def test_provider_settings_accepts_supported_backends(backend: str) -> None:
    settings = ProviderSettings(
        backend=backend,  # type: ignore[arg-type]
        base_url="http://localhost:8080/v1",
        chat_model="chat-model",
        embedding_model="embedding-model",
    )

    assert settings.backend == backend


@pytest.mark.parametrize(
    "settings",
    (
        {
            "backend": "unknown",
            "base_url": "http://localhost:8080/v1",
            "chat_model": "chat-model",
            "embedding_model": "embedding-model",
        },
        {
            "backend": "ollama",
            "base_url": "localhost:11434/api",
            "chat_model": "chat-model",
            "embedding_model": "embedding-model",
        },
        {
            "backend": "ollama",
            "base_url": "http://localhost:11434/api",
            "chat_model": " ",
            "embedding_model": "embedding-model",
        },
        {
            "backend": "ollama",
            "base_url": "http://localhost:11434/api",
            "chat_model": "chat-model",
            "embedding_model": "",
        },
    ),
)
def test_provider_settings_rejects_invalid_values(
    settings: dict[str, str],
) -> None:
    with pytest.raises(LLMProviderConfigurationError):
        ProviderSettings(**settings)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("backend", "provider_type"),
    (
        ("ollama", OllamaProvider),
        ("llama-cpp", LlamaCppProvider),
        ("openai-compatible", OpenAICompatibleProvider),
    ),
)
def test_build_llm_provider_selects_configured_backend(
    backend: str,
    provider_type: type[object],
) -> None:
    provider = build_llm_provider(
        ProviderSettings(
            backend=backend,  # type: ignore[arg-type]
            base_url="http://localhost:8080/v1",
            chat_model="chat-model",
            embedding_model="embedding-model",
            api_key="secret",
        )
    )

    assert isinstance(provider, provider_type)


def test_load_retrieval_settings_reads_exact_env_names() -> None:
    settings = load_retrieval_settings(
        {
            "RETRIEVAL_TOP_K": " 6 ",
            "RETRIEVAL_MIN_SCORE": " 0.25 ",
        }
    )

    assert settings == RetrievalSettings(top_k=6, min_score=0.25)


@pytest.mark.parametrize("missing_name", ("RETRIEVAL_TOP_K", "RETRIEVAL_MIN_SCORE"))
def test_load_retrieval_settings_requires_named_values(missing_name: str) -> None:
    env = {
        "RETRIEVAL_TOP_K": "6",
        "RETRIEVAL_MIN_SCORE": "0.25",
    }
    del env[missing_name]

    with pytest.raises(RetrievalConfigurationError):
        load_retrieval_settings(env)


@pytest.mark.parametrize(
    "settings",
    (
        {"top_k": 0, "min_score": 0.25},
        {"top_k": -1, "min_score": 0.25},
        {"top_k": True, "min_score": 0.25},
        {"top_k": 6, "min_score": -0.1},
        {"top_k": 6, "min_score": 1.1},
    ),
)
def test_retrieval_settings_rejects_invalid_values(
    settings: dict[str, int | float | bool],
) -> None:
    with pytest.raises(RetrievalConfigurationError):
        RetrievalSettings(**settings)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "env",
    (
        {"RETRIEVAL_TOP_K": "many", "RETRIEVAL_MIN_SCORE": "0.25"},
        {"RETRIEVAL_TOP_K": "6", "RETRIEVAL_MIN_SCORE": "high"},
    ),
)
def test_load_retrieval_settings_rejects_invalid_text(
    env: dict[str, str],
) -> None:
    with pytest.raises(RetrievalConfigurationError):
        load_retrieval_settings(env)
