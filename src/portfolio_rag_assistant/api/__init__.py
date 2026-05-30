"""Public HTTP API boundary."""

from portfolio_rag_assistant.api.app import create_api_app
from portfolio_rag_assistant.api.schemas import (
    MAX_QUESTION_LENGTH,
    MAX_REQUEST_BODY_BYTES,
    ChatRequestBody,
    ChatResponseBody,
    ChatSourceBody,
    ErrorBody,
    HealthResponseBody,
)

__all__ = [
    "MAX_QUESTION_LENGTH",
    "MAX_REQUEST_BODY_BYTES",
    "ChatRequestBody",
    "ChatResponseBody",
    "ChatSourceBody",
    "ErrorBody",
    "HealthResponseBody",
    "create_api_app",
]
