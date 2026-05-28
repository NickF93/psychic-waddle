"""Verified knowledge input contracts."""

from portfolio_rag_assistant.knowledge.input import (
    ALLOWED_KNOWLEDGE_CATEGORIES,
    CURRENT_KNOWLEDGE_SCHEMA_VERSION,
    FactInput,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeInputError,
    SourceInput,
    parse_knowledge_document,
)
from portfolio_rag_assistant.knowledge.ingestion import (
    KnowledgeBatch,
    KnowledgeChunk,
    KnowledgeIngestionError,
    build_fact_chunks,
    knowledge_batch_from_documents,
    load_knowledge_batch,
    load_knowledge_document,
    stable_chunk_index,
)
from portfolio_rag_assistant.knowledge.store import (
    KnowledgeStore,
    KnowledgeStoreError,
    connect_database,
)

__all__ = [
    "ALLOWED_KNOWLEDGE_CATEGORIES",
    "CURRENT_KNOWLEDGE_SCHEMA_VERSION",
    "FactInput",
    "KnowledgeBatch",
    "KnowledgeChunk",
    "KnowledgeCategory",
    "KnowledgeDocument",
    "KnowledgeIngestionError",
    "KnowledgeInputError",
    "KnowledgeStore",
    "KnowledgeStoreError",
    "SourceInput",
    "build_fact_chunks",
    "connect_database",
    "knowledge_batch_from_documents",
    "load_knowledge_batch",
    "load_knowledge_document",
    "parse_knowledge_document",
    "stable_chunk_index",
]
