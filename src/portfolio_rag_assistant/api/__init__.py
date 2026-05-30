"""Public HTTP API boundary."""

from portfolio_rag_assistant.api.app import create_api_app
from portfolio_rag_assistant.api.composition import (
    APICompositionError,
    build_public_chat_service,
    create_runtime_api_app,
)
from portfolio_rag_assistant.api.schemas import (
    MAX_QUESTION_LENGTH,
    MAX_REQUEST_BODY_BYTES,
    ChatRequestBody,
    ChatResponseBody,
    ChatSourceBody,
    ErrorBody,
    HealthResponseBody,
)
from portfolio_rag_assistant.api.service import ChatServiceError, PublicChatService

__all__ = [
    "MAX_QUESTION_LENGTH",
    "MAX_REQUEST_BODY_BYTES",
    "ChatRequestBody",
    "ChatResponseBody",
    "ChatSourceBody",
    "APICompositionError",
    "ErrorBody",
    "HealthResponseBody",
    "ChatServiceError",
    "PublicChatService",
    "build_public_chat_service",
    "create_api_app",
    "create_runtime_api_app",
]
