"""FastAPI application factory for the public API boundary."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from portfolio_rag_assistant.api.schemas import (
    MAX_REQUEST_BODY_BYTES,
    ChatRequestBody,
    ChatResponseBody,
    ErrorBody,
    HealthResponseBody,
)
from portfolio_rag_assistant.api.service import ChatServiceError


class ChatService(Protocol):
    """Small API-facing chat service surface."""

    def answer(self, request: ChatRequestBody) -> Awaitable[ChatResponseBody]: ...


class RequestSizeLimitMiddleware:
    """Reject oversized HTTP request bodies before endpoint handling."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
    ) -> None:
        if (
            not isinstance(max_body_bytes, int)
            or isinstance(max_body_bytes, bool)
            or max_body_bytes <= 0
        ):
            raise ValueError("max_body_bytes must be a positive integer")
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self._max_body_bytes:
            await _drain_body(receive)
            response = JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "request_too_large",
                        "message": "request body is too large",
                    }
                },
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)


def create_api_app(
    *,
    chat_service: ChatService | None = None,
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
) -> FastAPI:
    """Create the public API application with injected authorities."""

    app = FastAPI(title="Portfolio RAG Assistant API")
    app.state.chat_service = chat_service
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_bytes=max_body_bytes,
    )
    _register_error_handlers(app)
    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    @app.get("/health", response_model=HealthResponseBody)
    async def health() -> HealthResponseBody:
        return HealthResponseBody()

    @app.post("/chat", response_model=ChatResponseBody)
    async def chat(body: ChatRequestBody, request: Request) -> ChatResponseBody:
        service = _require_chat_service(request)
        return await service.answer(body)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="invalid_request",
            message="request is invalid",
        )

    @app.exception_handler(ChatServiceError)
    async def chat_service_error_handler(
        request: Request,
        error: ChatServiceError,
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            code="service_unavailable",
            message="chat service is unavailable",
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(
            status_code=500,
            code="internal_error",
            message="internal service error",
        )


def _require_chat_service(request: Request) -> ChatService:
    service = request.app.state.chat_service
    if service is None or not callable(getattr(service, "answer", None)):
        raise ChatServiceError("chat service is not configured")
    return service


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": ErrorBody(code=code, message=message).model_dump()},
    )


def _content_length(scope: Scope) -> int | None:
    headers = dict(scope.get("headers", ()))
    raw_value = headers.get(b"content-length")
    if raw_value is None:
        return None
    try:
        return int(raw_value.decode("ascii"))
    except ValueError:
        return None


async def _drain_body(receive: Receive) -> None:
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        if message["type"] == "http.request" and not message.get("more_body", False):
            return
