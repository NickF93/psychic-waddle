from __future__ import annotations

import pytest

from portfolio_rag_assistant.config import (
    ChatProviderSettings,
    DatabaseSettings,
    EmbeddingProviderSettings,
    RetrievalSettings,
    RuntimeConfigurationError,
    build_chat_provider,
    build_embedding_provider,
    load_chat_provider_settings,
    load_database_settings,
    load_embedding_provider_settings,
    load_retrieval_settings,
)
from portfolio_rag_assistant.provider import (
    LLMProviderConfigurationError,
    LlamaCppProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from portfolio_rag_assistant.retrieval import RetrievalConfigurationError


def test_load_chat_provider_settings_reads_exact_env_names() -> None:
    settings = load_chat_provider_settings(
        {
            "CHAT_BACKEND": "openai-compatible",
            "CHAT_BASE_URL": " https://provider.test/v1/ ",
            "CHAT_MODEL": " chat-model ",
            "CHAT_API_KEY": " chat-secret ",
        }
    )

    assert settings == ChatProviderSettings(
        backend="openai-compatible",
        base_url="https://provider.test/v1",
        model="chat-model",
        api_key="chat-secret",
    )


def test_load_embedding_provider_settings_reads_exact_env_names() -> None:
    settings = load_embedding_provider_settings(
        {
            "EMBEDDING_BACKEND": "ollama",
            "EMBEDDING_BASE_URL": " http://localhost:11434/api/ ",
            "EMBEDDING_MODEL": " nomic-embed-text ",
            "EMBEDDING_API_KEY": " ",
        }
    )

    assert settings == EmbeddingProviderSettings(
        backend="ollama",
        base_url="http://localhost:11434/api",
        model="nomic-embed-text",
        api_key=None,
    )


def test_chat_and_embedding_settings_can_use_the_same_endpoint() -> None:
    env = {
        "CHAT_BACKEND": "openai-compatible",
        "CHAT_BASE_URL": "https://api.example.test/v1",
        "CHAT_MODEL": "chat-model",
        "EMBEDDING_BACKEND": "openai-compatible",
        "EMBEDDING_BASE_URL": "https://api.example.test/v1",
        "EMBEDDING_MODEL": "embedding-model",
    }

    chat_settings = load_chat_provider_settings(env)
    embedding_settings = load_embedding_provider_settings(env)

    assert chat_settings.base_url == embedding_settings.base_url
    assert chat_settings.backend == embedding_settings.backend


def test_chat_and_embedding_settings_can_use_different_endpoints() -> None:
    chat_settings = load_chat_provider_settings(
        {
            "CHAT_BACKEND": "openai-compatible",
            "CHAT_BASE_URL": "https://api.example.test/v1",
            "CHAT_MODEL": "chat-model",
        }
    )
    embedding_settings = load_embedding_provider_settings(
        {
            "EMBEDDING_BACKEND": "ollama",
            "EMBEDDING_BASE_URL": "http://localhost:11434/api",
            "EMBEDDING_MODEL": "nomic-embed-text",
        }
    )

    assert chat_settings.backend == "openai-compatible"
    assert embedding_settings.backend == "ollama"


@pytest.mark.parametrize(
    "missing_name",
    ("CHAT_BACKEND", "CHAT_BASE_URL", "CHAT_MODEL"),
)
def test_load_chat_provider_settings_requires_named_values(
    missing_name: str,
) -> None:
    env = {
        "CHAT_BACKEND": "openai-compatible",
        "CHAT_BASE_URL": "https://api.example.test/v1",
        "CHAT_MODEL": "chat-model",
    }
    del env[missing_name]

    with pytest.raises(LLMProviderConfigurationError):
        load_chat_provider_settings(env)


@pytest.mark.parametrize(
    "missing_name",
    ("EMBEDDING_BACKEND", "EMBEDDING_BASE_URL", "EMBEDDING_MODEL"),
)
def test_load_embedding_provider_settings_requires_named_values(
    missing_name: str,
) -> None:
    env = {
        "EMBEDDING_BACKEND": "ollama",
        "EMBEDDING_BASE_URL": "http://localhost:11434/api",
        "EMBEDDING_MODEL": "nomic-embed-text",
    }
    del env[missing_name]

    with pytest.raises(LLMProviderConfigurationError):
        load_embedding_provider_settings(env)


@pytest.mark.parametrize(
    "settings",
    (
        {
            "backend": "unknown",
            "base_url": "http://localhost:8080/v1",
            "model": "model",
        },
        {
            "backend": "ollama",
            "base_url": "localhost:11434/api",
            "model": "model",
        },
        {
            "backend": "ollama",
            "base_url": "http://localhost:11434/api",
            "model": " ",
        },
    ),
)
def test_provider_settings_reject_invalid_values(
    settings: dict[str, str],
) -> None:
    with pytest.raises(LLMProviderConfigurationError):
        ChatProviderSettings(**settings)  # type: ignore[arg-type]
    with pytest.raises(LLMProviderConfigurationError):
        EmbeddingProviderSettings(**settings)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("backend", "provider_type"),
    (
        ("ollama", OllamaProvider),
        ("llama-cpp", LlamaCppProvider),
        ("openai-compatible", OpenAICompatibleProvider),
    ),
)
def test_build_chat_provider_selects_configured_backend(
    backend: str,
    provider_type: type[object],
) -> None:
    provider = build_chat_provider(
        ChatProviderSettings(
            backend=backend,  # type: ignore[arg-type]
            base_url="http://localhost:8080/v1",
            model="chat-model",
            api_key="secret",
        )
    )

    assert isinstance(provider, provider_type)


@pytest.mark.parametrize(
    ("backend", "provider_type"),
    (
        ("ollama", OllamaProvider),
        ("llama-cpp", LlamaCppProvider),
        ("openai-compatible", OpenAICompatibleProvider),
    ),
)
def test_build_embedding_provider_selects_configured_backend(
    backend: str,
    provider_type: type[object],
) -> None:
    provider = build_embedding_provider(
        EmbeddingProviderSettings(
            backend=backend,  # type: ignore[arg-type]
            base_url="http://localhost:8080/v1",
            model="embedding-model",
            api_key="secret",
        )
    )

    assert isinstance(provider, provider_type)


def test_load_database_settings_reads_exact_env_names() -> None:
    settings = load_database_settings(
        {
            "DB_HOST": " db ",
            "DB_PORT": " 5432 ",
            "DB_NAME": " portfolio ",
            "DB_USER": " portfolio_user ",
            "DB_PASSWORD": " p@ss/word:% ",
        }
    )

    assert settings == DatabaseSettings(
        host="db",
        port=5432,
        name="portfolio",
        user="portfolio_user",
        password="p@ss/word:%",
    )


@pytest.mark.parametrize(
    "missing_name",
    ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"),
)
def test_load_database_settings_requires_named_values(missing_name: str) -> None:
    env = {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "portfolio",
        "DB_USER": "portfolio_user",
        "DB_PASSWORD": "secret",
    }
    del env[missing_name]

    with pytest.raises(RuntimeConfigurationError):
        load_database_settings(env)


@pytest.mark.parametrize(
    "settings",
    (
        {"host": "db", "port": 0, "name": "portfolio", "user": "user", "password": "x"},
        {
            "host": "db",
            "port": 65536,
            "name": "portfolio",
            "user": "user",
            "password": "x",
        },
        {
            "host": "db",
            "port": True,
            "name": "portfolio",
            "user": "user",
            "password": "x",
        },
        {"host": " ", "port": 5432, "name": "portfolio", "user": "user", "password": "x"},
    ),
)
def test_database_settings_reject_invalid_values(
    settings: dict[str, str | int | bool],
) -> None:
    with pytest.raises(RuntimeConfigurationError):
        DatabaseSettings(**settings)  # type: ignore[arg-type]


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
