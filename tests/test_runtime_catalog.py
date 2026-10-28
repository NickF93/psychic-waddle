from copy import deepcopy

import pytest

from portfolio_rag_assistant.runtime_catalog import CatalogExportError, export_catalog

ENV = {
    "CHAT_BACKEND": "ollama",
    "EMBEDDING_BACKEND": "ollama",
    "CHAT_BASE_URL": "http://provider:11434/api",
    "EMBEDDING_BASE_URL": "http://provider:11434/api",
    "CHAT_MODEL": "chat:small",
    "EMBEDDING_MODEL": "embedding",
    "CHAT_API_KEY": "never-export-this",
}


def fixture():
    return {
        "chat:small": {
            "capabilities": ["completion", "tools"],
            "model_info": {
                "general.architecture": "chat",
                "chat.context_length": 32768,
            },
        },
        "embedding": {
            "parameters": "num_ctx 8192",
            "capabilities": ["embedding"],
            "model_info": {
                "general.architecture": "embed",
                "embed.context_length": 2048,
                "embed.embedding_length": 768,
            },
        },
    }


def export(env=None, documents=None, **kwargs):
    documents = documents or fixture()
    calls = []

    def read(base, path, payload=None):
        calls.append((path, payload))
        if path == "/api/tags":
            return {
                "models": [
                    {"name": "chat:small", "digest": "a" * 64},
                    {"name": "embedding:latest", "digest": "b" * 64},
                    {"name": "unselected:latest", "digest": "c" * 64},
                ]
            }
        assert path == "/api/show"
        return documents[payload["model"]]

    values = {
        "source_commit": "d" * 40,
        "chat_context": 4096,
        "chat_output": 1024,
        "embedding_context": 2048,
    }
    values.update(kwargs)
    return export_catalog(env or ENV, read=read, **values), calls


def test_export_contains_only_selected_roles_and_native_limits():
    result, calls = export()
    assert [m["native_id"] for m in result["models"]] == ["chat:small", "embedding"]
    assert result["models"][0]["context_window"] == 4096
    assert result["models"][1]["context_window"] == 2048
    assert result["models"][1]["embedding_dimensions"] == 768
    assert result["models"][1]["max_output_tokens"] is None
    assert "never-export-this" not in str(result)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"chat_context": 65536},
        {"embedding_context": 8192},
        {"chat_output": 8192},
        {"source_commit": "develop"},
    ],
)
def test_export_rejects_unsubstantiated_limits(changes):
    with pytest.raises(CatalogExportError):
        export(**changes)


def test_export_rejects_role_mismatch():
    docs = deepcopy(fixture())
    docs["embedding"]["capabilities"] = ["completion"]
    with pytest.raises(CatalogExportError):
        export(documents=docs)


def test_export_requires_the_actual_configured_provider():
    with pytest.raises(CatalogExportError):
        export(env={**ENV, "CHAT_BACKEND": "openai-compatible"})


def test_external_primary_exports_only_the_explicit_local_fallback():
    result, _ = export(env={**ENV, "CHAT_BACKEND": "openai-compatible", "CHAT_MODEL": "external-model",
        "CHAT_BASE_URL": "https://external.invalid/v1", "CHAT_FALLBACK_BACKEND": "ollama",
        "CHAT_FALLBACK_BASE_URL": ENV["CHAT_BASE_URL"], "CHAT_FALLBACK_MODEL": ENV["CHAT_MODEL"]})
    assert [model["native_id"] for model in result["models"]] == ["chat:small", "embedding"]
    assert "external-model" not in str(result)
