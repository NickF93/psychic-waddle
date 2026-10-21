"""Behavioral regressions for target mapping, completion and input admission."""

import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from portfolio_rag_assistant.provider.contract import (
    ChatMessage,
    ChatRequest,
    LLMInputBudgetError,
    LLMProviderConfigurationError,
    LLMProviderRequestError,
    LLMProviderResponseError,
)
from portfolio_rag_assistant.provider.parameters import ParameterProfile, chat_payload
from portfolio_rag_assistant.provider.budget import InputBudget
from portfolio_rag_assistant.provider import (
    OpenAICompatibleProvider,
    OllamaProvider,
    LlamaCppProvider,
)
from portfolio_rag_assistant.config import (
    load_chat_provider_settings,
    load_fallback_chat_provider_settings,
)
from test_generation_delivery import Provider, REQUEST
from portfolio_rag_assistant.answer import GroundedAnswerGenerator

BASE = ChatRequest(
    model="selected",
    messages=(ChatMessage("user", "approved information"),),
    max_tokens=384,
)


@pytest.mark.parametrize(
    "name",
    [
        "openai",
        "openai-effort",
        "openai-reasoning",
        "ollama",
        "portfolio-primary",
        "portfolio-local",
    ],
)
def test_every_bundled_profile_is_valid(name):
    ParameterProfile.load(name).encode(BASE)


@pytest.mark.parametrize("stream", [False, True])
def test_reasoning_configuration_maps_without_replacing_identity(stream):
    request = replace(BASE, reasoning_mode="on", reasoning_effort="low")
    body = chat_payload(
        request, stream=stream, profile=ParameterProfile.load("portfolio-primary")
    )
    assert body["reasoning"] == {"enabled": True, "effort": "low"}
    assert body["model"] == "selected" and body["stream"] is stream
    assert body["max_tokens"] == 384
    assert "temperature" not in body and "top_p" not in body


@pytest.mark.parametrize(
    "name,expected",
    [
        ("openai-reasoning", {"reasoning": {"enabled": False}}),
        ("ollama", {"think": False}),
    ],
)
def test_reasoning_can_really_be_disabled_when_declared(name, expected):
    encoded = ParameterProfile.load(name).encode(
        replace(BASE, reasoning_mode="off", max_tokens=None)
    )
    assert encoded == expected


def test_native_effort_replaces_boolean_thinking_control():
    body = ParameterProfile.load("ollama").encode(
        replace(BASE, reasoning_mode="on", reasoning_effort="low")
    )
    assert body["think"] == "low"


@pytest.mark.parametrize(
    "options",
    [
        {"reasoning_mode": "off"},
        {"temperature": 0},
        {"top_p": 0.9},
        {"reasoning_mode": "on", "reasoning_effort": "unknown"},
    ],
)
def test_target_rejects_unsupported_controls(options):
    with pytest.raises(LLMProviderConfigurationError):
        ParameterProfile.load("portfolio-primary").encode(replace(BASE, **options))


@pytest.mark.parametrize(
    "options",
    [
        {"reasoning_mode": "off", "reasoning_effort": "low"},
        {"temperature": True},
        {"temperature": float("nan")},
        {"top_p": True},
        {"top_p": float("inf")},
    ],
)
def test_invalid_normalized_options_fail(options):
    with pytest.raises(ValueError):
        replace(BASE, **options)


def test_primary_and_fallback_options_are_independent():
    env = {
        "CHAT_BACKEND": "openai-compatible",
        "CHAT_BASE_URL": "https://example.test/v1",
        "CHAT_MODEL": "primary",
        "CHAT_PARAMETER_PROFILE": "portfolio-primary",
        "CHAT_REASONING_MODE": "on",
        "CHAT_REASONING_EFFORT": "low",
        "CHAT_MAX_TOKENS": "4096",
        "CHAT_FALLBACK_BACKEND": "ollama",
        "CHAT_FALLBACK_BASE_URL": "http://local/api",
        "CHAT_FALLBACK_MODEL": "local",
        "CHAT_FALLBACK_TEMPERATURE": "0",
        "CHAT_FALLBACK_PARAMETER_PROFILE": "portfolio-local",
    }
    primary = load_chat_provider_settings(env)
    fallback = load_fallback_chat_provider_settings(env)
    assert primary.reasoning_effort == "low" and primary.max_tokens == 4096
    assert fallback.reasoning_mode == "default" and fallback.reasoning_effort is None
    assert fallback.temperature == 0 and fallback.max_tokens == 384


@pytest.mark.parametrize(
    "mapping",
    [
        {"model": "model"},
        {"max_tokens": "messages"},
        {"temperature": "stream"},
        {"max_tokens": "options", "top_p": "options.top_p"},
    ],
)
def test_unsafe_or_conflicting_mapping_is_rejected(tmp_path, mapping):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"bad": {"paths": mapping, "reasoning": {}, "efforts": []}})
    )
    with pytest.raises(LLMProviderConfigurationError):
        ParameterProfile.load("bad", path)


@pytest.mark.parametrize("provider_type", [OpenAICompatibleProvider, LlamaCppProvider])
@pytest.mark.parametrize("reason", [None, "length", "content_filter", "tool_calls"])
def test_non_streaming_incomplete_answer_is_never_accepted(provider_type, reason):
    payload = {
        "model": "selected",
        "choices": [
            {
                "message": {"role": "assistant", "content": "partial answer"},
                "finish_reason": reason,
            }
        ],
    }
    provider = provider_type(
        base_url="http://fixture/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    )
    with pytest.raises(LLMProviderResponseError):
        asyncio.run(provider.chat(BASE))


@pytest.mark.parametrize(
    "provider_type", [OpenAICompatibleProvider, LlamaCppProvider, OllamaProvider]
)
@pytest.mark.parametrize("status", [401, 429, 503])
def test_status_survives_without_upstream_body(provider_type, status):
    provider = provider_type(
        base_url="http://fixture/api",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(status, text="secret credential and question")
        ),
    )
    with pytest.raises(LLMProviderRequestError) as failure:
        asyncio.run(provider.chat(BASE))
    assert failure.value.status_code == status
    assert "secret" not in str(failure.value)


def test_utf8_limit_counts_bytes_not_characters_and_reserves_output():
    request = replace(BASE, messages=(ChatMessage("user", "éé"),), max_tokens=10)
    InputBudget(max_bytes=4, context_tokens=270).check(request)
    with pytest.raises(LLMInputBudgetError):
        InputBudget(max_bytes=3).check(request)
    with pytest.raises(LLMInputBudgetError):
        InputBudget(max_bytes=4, context_tokens=269).check(request)


@pytest.mark.parametrize("stream", [False, True])
def test_oversize_fallback_does_not_dispatch_or_remove_evidence(stream):
    primary = Provider([RuntimeError("unused")])
    fallback = Provider(["answer"])
    generator = GroundedAnswerGenerator(
        primary,
        "remote",
        input_budget=InputBudget(max_bytes=1),
        fallback_provider=fallback,
        fallback_model="local",
        fallback_input_budget=InputBudget(max_bytes=1),
    )

    async def run():
        return (
            [event async for event in generator.stream(REQUEST)]
            if stream
            else await generator.generate(REQUEST)
        )

    with pytest.raises(LLMInputBudgetError):
        asyncio.run(run())
    assert primary.calls == fallback.calls == 0


def test_model_tokenizer_counts_input_without_automatic_truncation(tmp_path):
    from tokenizers import Tokenizer, models, pre_tokenizers

    tokenizer = Tokenizer(
        models.WordLevel(
            {"[UNK]": 0, "approved": 1, "information": 2}, unk_token="[UNK]"
        )
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.enable_truncation(1)
    path = tmp_path / "tokenizer.json"
    tokenizer.save(str(path))
    InputBudget(context_tokens=642, tokenizer_path=str(path)).check(BASE)
    with pytest.raises(LLMInputBudgetError):
        InputBudget(context_tokens=641, tokenizer_path=str(path)).check(BASE)


@pytest.mark.parametrize(
    "provider_type", [OpenAICompatibleProvider, OllamaProvider, LlamaCppProvider]
)
def test_embeddings_do_not_require_chat_configuration(provider_type, monkeypatch):
    from portfolio_rag_assistant.provider.contract import EmbeddingRequest

    def unavailable(*args, **kwargs):
        raise AssertionError("embedding I/O must not load chat configuration")

    monkeypatch.setattr(ParameterProfile, "load", unavailable)
    native = provider_type is OllamaProvider
    payload = (
        {"model": "embedding", "embeddings": [[1.0, 2.0]]}
        if native
        else {"model": "embedding", "data": [{"index": 0, "embedding": [1.0, 2.0]}]}
    )
    provider = provider_type(
        base_url="http://fixture/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
    )
    result = asyncio.run(
        provider.embed(EmbeddingRequest(model="embedding", inputs=("text",)))
    )
    assert result.embeddings == ((1.0, 2.0),)


@pytest.mark.parametrize("prefix", ["CHAT_", "CHAT_FALLBACK_"])
@pytest.mark.parametrize("field", ["INPUT_MAX_BYTES", "CONTEXT_TOKENS"])
@pytest.mark.parametrize("value", ["invalid", "0"])
def test_invalid_input_limit_identifies_the_actual_target_setting(prefix, field, value):
    env = {
        prefix + "BACKEND": "ollama",
        prefix + "BASE_URL": "http://fixture/api",
        prefix + "MODEL": "local",
        prefix + field: value,
    }
    loader = (
        load_chat_provider_settings
        if prefix == "CHAT_"
        else load_fallback_chat_provider_settings
    )
    with pytest.raises(LLMProviderConfigurationError, match=prefix + field):
        loader(env)
