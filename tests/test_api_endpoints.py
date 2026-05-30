from __future__ import annotations

import asyncio

import httpx

from portfolio_rag_assistant.api import (
    ChatRequestBody,
    ChatResponseBody,
    ChatServiceError,
    ChatSourceBody,
    create_api_app,
)


def test_health_endpoint_returns_ok() -> None:
    response = _request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_returns_ready_when_runtime_checks_pass() -> None:
    response = _request("GET", "/ready", readiness_service=ReadyService())

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_endpoint_returns_service_error_when_runtime_is_not_ready() -> None:
    response = _request("GET", "/ready", readiness_service=NotReadyService())

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "service is not ready",
        }
    }
    assert "schema missing" not in response.text


def test_ready_endpoint_requires_configured_readiness_service() -> None:
    response = _request("GET", "/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_chat_endpoint_returns_answerable_response() -> None:
    service = FakeChatService(
        ChatResponseBody(
            status="answerable",
            answer="Niccolo worked at NAIS s.r.l.\n\nSources: CV.",
            sources=(
                ChatSourceBody(
                    title="Niccolo Ferrari CV",
                    locator="Experience section",
                ),
            ),
        )
    )
    response = _request(
        "POST",
        "/chat",
        json={"question": " Where did Niccolo work? ", "language": "en"},
        chat_service=service,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "answerable",
        "answer": "Niccolo worked at NAIS s.r.l.\n\nSources: CV.",
        "sources": [
            {
                "title": "Niccolo Ferrari CV",
                "locator": "Experience section",
            }
        ],
    }
    assert service.requests == (
        ChatRequestBody(question="Where did Niccolo work?", language="en"),
    )
    assert "cv://niccolo/main" not in response.text


def test_chat_endpoint_returns_not_answerable_response() -> None:
    response = _request(
        "POST",
        "/chat",
        json={"question": "Private phone?", "language": "en"},
        chat_service=FakeChatService(
            ChatResponseBody(
                status="not_answerable",
                answer="I do not have verified public context.",
            )
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_answerable",
        "answer": "I do not have verified public context.",
        "sources": [],
    }


def test_chat_endpoint_returns_stable_validation_error() -> None:
    response = _request(
        "POST",
        "/chat",
        json={"question": " ", "language": "fr"},
        chat_service=FakeChatService.unused(),
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "request is invalid",
        }
    }
    assert "question must not be blank" not in response.text


def test_chat_endpoint_returns_stable_service_error() -> None:
    response = _request(
        "POST",
        "/chat",
        json={"question": "Where did Niccolo work?", "language": "en"},
        chat_service=UnavailableChatService(),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "chat service is unavailable",
        }
    }
    assert "database password" not in response.text


def test_chat_endpoint_returns_sanitized_internal_error() -> None:
    response = _request(
        "POST",
        "/chat",
        json={"question": "Where did Niccolo work?", "language": "en"},
        chat_service=ExplodingChatService(),
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "internal service error",
        }
    }
    assert "provider stack trace" not in response.text


def test_chat_endpoint_requires_configured_chat_service() -> None:
    response = _request(
        "POST",
        "/chat",
        json={"question": "Where did Niccolo work?", "language": "en"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def _request(
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
    chat_service: object | None = None,
    readiness_service: object | None = None,
) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(
            app=create_api_app(
                chat_service=chat_service,
                readiness_service=readiness_service,
            ),
            raise_app_exceptions=False,
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(run())


class FakeChatService:
    def __init__(self, response: ChatResponseBody) -> None:
        self._response = response
        self.requests: tuple[ChatRequestBody, ...] = ()

    async def answer(self, request: ChatRequestBody) -> ChatResponseBody:
        self.requests = (*self.requests, request)
        return self._response

    @classmethod
    def unused(cls) -> FakeChatService:
        return cls(
            ChatResponseBody(
                status="not_answerable",
                answer="unused",
            )
        )


class UnavailableChatService:
    async def answer(self, request: ChatRequestBody) -> ChatResponseBody:
        raise ChatServiceError("database password leaked")


class ExplodingChatService:
    async def answer(self, request: ChatRequestBody) -> ChatResponseBody:
        raise RuntimeError("provider stack trace leaked")


class ReadyService:
    async def check(self) -> None:
        return None


class NotReadyService:
    async def check(self) -> None:
        raise RuntimeError("schema missing")
