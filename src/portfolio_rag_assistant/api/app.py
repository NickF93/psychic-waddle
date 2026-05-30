"""FastAPI application factory for the public API boundary."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from portfolio_rag_assistant.api.schemas import MAX_REQUEST_BODY_BYTES


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
    chat_service: object | None = None,
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
) -> FastAPI:
    """Create the public API application with injected authorities."""

    app = FastAPI(title="Portfolio RAG Assistant API")
    app.state.chat_service = chat_service
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_bytes=max_body_bytes,
    )
    return app


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
