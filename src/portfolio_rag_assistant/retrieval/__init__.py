"""Retrieval authority contracts."""

from portfolio_rag_assistant.retrieval.contract import (
    RetrievedContext,
    RetrievalConfigurationError,
    RetrievalError,
    RetrievalRequest,
    RetrievalRequestError,
    RetrievalResponse,
    RetrievalScore,
    RetrievalStoreError,
    Retriever,
)
from portfolio_rag_assistant.retrieval.postgres import PostgreSQLRetriever

__all__ = [
    "PostgreSQLRetriever",
    "RetrievedContext",
    "RetrievalConfigurationError",
    "RetrievalError",
    "RetrievalRequest",
    "RetrievalRequestError",
    "RetrievalResponse",
    "RetrievalScore",
    "RetrievalStoreError",
    "Retriever",
]
