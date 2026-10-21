import asyncio
import json

import httpx
import pytest

from portfolio_rag_assistant.provider import ChatMessage, ChatRequest
from portfolio_rag_assistant.provider.openai_compatible import OpenAICompatibleProvider
from portfolio_rag_assistant.provider.ollama import OllamaProvider
from portfolio_rag_assistant.provider.contract import LLMProviderError

REQUEST = ChatRequest(
    model="configured-model", messages=(ChatMessage(role="user", content="Question"),)
)


def collect(provider):
    async def run():
        return [item async for item in provider.stream_chat(REQUEST)]

    return asyncio.run(run())


def sse(*chunks):
    return "".join(
        "data: " + (json.dumps(item) if isinstance(item, dict) else item) + "\n\n"
        for item in chunks
    )


def choice(content=None, reason=None, **delta):
    if content is not None:
        delta["content"] = content
    return {"choices": [{"delta": delta, "finish_reason": reason}]}


@pytest.mark.parametrize("key", [None, "server-secret"])
def test_openai_stream_optional_auth_content_only_and_usage(key):
    def handler(request):
        assert json.loads(request.content)["stream"] is True
        assert request.headers.get("authorization") == (
            f"Bearer {key}" if key else None
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(
                choice(role="assistant"),
                choice(reasoning_content="private reasoning"),
                choice("Hello "),
                choice("world"),
                choice(reason="stop"),
                {"choices": [], "usage": {"total_tokens": 5}},
                "[DONE]",
            ),
        )

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key=key,
        transport=httpx.MockTransport(handler),
    )
    assert collect(provider) == ["Hello ", "world"]


@pytest.mark.parametrize(
    "body",
    [
        sse(choice("partial")),
        sse("[DONE]"),
        sse(choice("partial"), choice(reason="length")),
        sse({"error": {"message": "secret"}}),
        "data: invalid\n\n",
    ],
)
def test_openai_rejects_incomplete_or_invalid_streams(body):
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, text=body
            )
        ),
    )
    with pytest.raises(LLMProviderError):
        collect(provider)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_stream_http_errors_never_expose_response_bodies(status):
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, text="secret question and credential"
            )
        ),
    )
    with pytest.raises(LLMProviderError) as failure:
        collect(provider)
    assert "secret" not in str(failure.value)


def test_ollama_stream_requires_done_and_keeps_last_content():
    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            text='{"message":{"thinking":"private","content":"Hello"},"done":false}\n'
            '{"message":{"content":"!"},"done":true,"done_reason":"stop"}\n',
        )

    assert collect(
        OllamaProvider(
            base_url="http://ollama.test/api", transport=httpx.MockTransport(handler)
        )
    ) == ["Hello", "!"]


def test_ollama_eof_is_not_completion():
    provider = OllamaProvider(
        base_url="http://ollama.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text='{"message":{"content":"partial"},"done":false}\n'
            )
        ),
    )
    with pytest.raises(LLMProviderError):
        collect(provider)
