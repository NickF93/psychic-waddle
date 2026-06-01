"""Runtime composition for the public API."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from portfolio_rag_assistant.answer import GroundedAnswerGenerator
from portfolio_rag_assistant.api.app import create_api_app
from portfolio_rag_assistant.api.readiness import DatabaseReadinessService
from portfolio_rag_assistant.api.service import PublicChatService
from portfolio_rag_assistant.config import (
    ChatProviderSettings,
    DatabaseSettings,
    EmbeddingProviderSettings,
    build_chat_provider,
    build_embedding_provider,
    load_chat_provider_settings,
    load_database_settings,
    load_embedding_provider_settings,
    load_question_collection_settings,
    load_retrieval_settings,
)
from portfolio_rag_assistant.knowledge import connect_database
from portfolio_rag_assistant.policy import DeterministicAnswerPolicy
from portfolio_rag_assistant.provider import ChatProvider, EmbeddingProvider
from portfolio_rag_assistant.questions import (
    DisabledQuestionCollector,
    PostgreSQLQuestionCollector,
)
from portfolio_rag_assistant.retrieval import PostgreSQLRetriever

ChatProviderFactory = Callable[[ChatProviderSettings], ChatProvider]
EmbeddingProviderFactory = Callable[[EmbeddingProviderSettings], EmbeddingProvider]
ConnectionFactory = Callable[[DatabaseSettings], Any]


class APICompositionError(RuntimeError):
    """Raised when the runtime API cannot be composed."""


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    """Composed services exposed by the ASGI application."""

    chat_service: PublicChatService
    readiness_service: DatabaseReadinessService


def _connect_database(settings: DatabaseSettings) -> Any:
    try:
        return connect_database(
            host=settings.host,
            port=settings.port,
            name=settings.name,
            user=settings.user,
            password=settings.password,
        )
    except Exception as error:
        raise APICompositionError("database connection failed") from error


def create_runtime_api_app(
    *,
    env: Mapping[str, str] | None = None,
    chat_provider_factory: ChatProviderFactory = build_chat_provider,
    embedding_provider_factory: EmbeddingProviderFactory = build_embedding_provider,
    connection_factory: ConnectionFactory = _connect_database,
) -> FastAPI:
    """Create the ASGI API application from explicit runtime configuration."""

    services = build_runtime_services(
        env=env,
        chat_provider_factory=chat_provider_factory,
        embedding_provider_factory=embedding_provider_factory,
        connection_factory=connection_factory,
    )
    return create_api_app(
        chat_service=services.chat_service,
        readiness_service=services.readiness_service,
    )


def build_public_chat_service(
    *,
    env: Mapping[str, str] | None = None,
    chat_provider_factory: ChatProviderFactory = build_chat_provider,
    embedding_provider_factory: EmbeddingProviderFactory = build_embedding_provider,
    connection_factory: ConnectionFactory = _connect_database,
) -> PublicChatService:
    """Compose the public chat service from configured authorities."""

    return build_runtime_services(
        env=env,
        chat_provider_factory=chat_provider_factory,
        embedding_provider_factory=embedding_provider_factory,
        connection_factory=connection_factory,
    ).chat_service


def build_runtime_services(
    *,
    env: Mapping[str, str] | None = None,
    chat_provider_factory: ChatProviderFactory = build_chat_provider,
    embedding_provider_factory: EmbeddingProviderFactory = build_embedding_provider,
    connection_factory: ConnectionFactory = _connect_database,
) -> RuntimeServices:
    """Compose public chat and readiness services from runtime configuration."""

    environment = os.environ if env is None else env
    database_settings = load_database_settings(environment)
    chat_settings = load_chat_provider_settings(environment)
    embedding_settings = load_embedding_provider_settings(environment)
    retrieval_settings = load_retrieval_settings(environment)
    question_collection_settings = load_question_collection_settings(environment)
    chat_provider = chat_provider_factory(chat_settings)
    embedding_provider = embedding_provider_factory(embedding_settings)
    connection = connection_factory(database_settings)
    question_collector = (
        PostgreSQLQuestionCollector(connection)
        if question_collection_settings.enabled
        else DisabledQuestionCollector()
    )
    retriever = PostgreSQLRetriever(
        connection=connection,
        provider=embedding_provider,
        embedding_backend=embedding_settings.backend,
        embedding_model=embedding_settings.model,
        min_score=retrieval_settings.min_score,
    )
    return RuntimeServices(
        chat_service=PublicChatService(
            retriever=retriever,
            answer_policy=DeterministicAnswerPolicy(),
            answer_generator=GroundedAnswerGenerator(
                provider=chat_provider,
                chat_model=chat_settings.model,
            ),
            question_collector=question_collector,
            retrieval_settings=retrieval_settings,
        ),
        readiness_service=DatabaseReadinessService(
            connection=connection,
            embedding_backend=embedding_settings.backend,
            embedding_model=embedding_settings.model,
        ),
    )
