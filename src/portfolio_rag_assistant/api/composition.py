"""Runtime composition for the public API."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import FastAPI

from portfolio_rag_assistant.answer import GroundedAnswerGenerator
from portfolio_rag_assistant.api.app import create_api_app
from portfolio_rag_assistant.api.service import PublicChatService
from portfolio_rag_assistant.config import (
    ProviderSettings,
    build_llm_provider,
    load_provider_settings,
    load_retrieval_settings,
)
from portfolio_rag_assistant.knowledge import connect_database
from portfolio_rag_assistant.policy import DeterministicAnswerPolicy
from portfolio_rag_assistant.provider import LLMProvider
from portfolio_rag_assistant.retrieval import PostgreSQLRetriever

ProviderFactory = Callable[[ProviderSettings], LLMProvider]
ConnectionFactory = Callable[[str], Any]


class APICompositionError(RuntimeError):
    """Raised when the runtime API cannot be composed."""


def create_runtime_api_app(
    *,
    env: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = build_llm_provider,
    connection_factory: ConnectionFactory = connect_database,
) -> FastAPI:
    """Create the ASGI API application from explicit runtime configuration."""

    return create_api_app(
        chat_service=build_public_chat_service(
            env=env,
            provider_factory=provider_factory,
            connection_factory=connection_factory,
        )
    )


def build_public_chat_service(
    *,
    env: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = build_llm_provider,
    connection_factory: ConnectionFactory = connect_database,
) -> PublicChatService:
    """Compose the public chat service from configured authorities."""

    environment = os.environ if env is None else env
    database_url = _require_env(environment, "DATABASE_URL")
    provider_settings = load_provider_settings(environment)
    retrieval_settings = load_retrieval_settings(environment)
    provider = provider_factory(provider_settings)
    connection = connection_factory(database_url)
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=provider,
        embedding_backend=provider_settings.backend,
        embedding_model=provider_settings.embedding_model,
        min_score=retrieval_settings.min_score,
    )
    return PublicChatService(
        retriever=retriever,
        answer_policy=DeterministicAnswerPolicy(),
        answer_generator=GroundedAnswerGenerator(
            provider=provider,
            chat_model=provider_settings.chat_model,
        ),
        retrieval_settings=retrieval_settings,
    )


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise APICompositionError(f"{name} must be set")
    return value.strip()
