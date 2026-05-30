from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_uses_pinned_base_and_locked_dependencies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim@sha256:" in dockerfile
    assert "requirements.lock" in dockerfile
    assert "pip install --constraint requirements.lock ." in dockerfile
    assert "pip install --upgrade pip" not in dockerfile
    assert "USER app" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "portfolio_rag_assistant.api.main:app" in dockerfile
    assert ".env" not in dockerfile


def test_requirements_lock_pins_runtime_dependencies() -> None:
    requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")

    assert "fastapi==" in requirements
    assert "httpx==" in requirements
    assert "psycopg==" in requirements
    assert "psycopg-binary==" in requirements
    assert "uvicorn==" in requirements
    assert ">=" not in requirements
    assert "<" not in requirements


def test_compose_uses_pinned_images_and_private_runtime_network() -> None:
    services = _compose()["services"]

    assert services["db"]["image"].startswith("pgvector/pgvector:0.8.2-pg17@sha256:")
    assert services["ollama"]["image"].startswith("ollama/ollama:latest@sha256:")
    assert services["llama-cpp-chat"]["image"].startswith(
        "ghcr.io/ggml-org/llama.cpp:server@sha256:"
    )
    assert services["llama-cpp-embeddings"]["image"].startswith(
        "ghcr.io/ggml-org/llama.cpp:server@sha256:"
    )
    assert _compose()["networks"]["runtime"]["driver"] == "bridge"


def test_compose_api_uses_capability_specific_config_without_database_url() -> None:
    environment = _compose()["services"]["api"]["environment"]

    assert "DATABASE_URL" not in environment
    assert "LLM_BACKEND" not in environment
    assert "LLM_BASE_URL" not in environment
    assert "LLM_API_KEY" not in environment
    assert environment["DB_HOST"] == "db"
    assert environment["DB_PORT"] == "5432"
    assert environment["DB_NAME"] == "${POSTGRES_DB}"
    assert environment["DB_USER"] == "${POSTGRES_USER}"
    assert environment["DB_PASSWORD"] == "${POSTGRES_PASSWORD}"
    assert environment["CHAT_BACKEND"] == "${CHAT_BACKEND}"
    assert environment["CHAT_BASE_URL"] == "${CHAT_BASE_URL}"
    assert environment["EMBEDDING_BACKEND"] == "${EMBEDDING_BACKEND}"
    assert environment["EMBEDDING_BASE_URL"] == "${EMBEDDING_BASE_URL}"


def test_compose_keeps_api_port_localhost_by_default() -> None:
    ports = _compose()["services"]["api"]["ports"]

    assert ports == ["${API_BIND_ADDRESS:-127.0.0.1}:${API_PORT:-8000}:8000"]


def test_compose_keeps_healthcheck_as_liveness_only() -> None:
    healthcheck = _compose()["services"]["api"]["healthcheck"]

    assert "/health" in healthcheck["test"][-1]
    assert "/ready" not in healthcheck["test"][-1]


def test_compose_local_llms_are_profile_gated() -> None:
    services = _compose()["services"]

    assert services["ollama"]["profiles"] == ["ollama"]
    assert services["llama-cpp-chat"]["profiles"] == ["llama-cpp"]
    assert services["llama-cpp-embeddings"]["profiles"] == ["llama-cpp"]


def test_llama_cpp_profile_has_separate_chat_and_embedding_servers() -> None:
    services = _compose()["services"]
    chat_command = services["llama-cpp-chat"]["command"]
    embedding_command = services["llama-cpp-embeddings"]["command"]

    assert services["llama-cpp-chat"]["volumes"] == services[
        "llama-cpp-embeddings"
    ]["volumes"]
    assert "${LLAMA_CPP_CHAT_MODEL_PATH}" in chat_command
    assert "--embedding" not in chat_command
    assert "${LLAMA_CPP_EMBEDDING_MODEL_PATH}" in embedding_command
    assert "--embedding" in embedding_command
    assert "--pooling" in embedding_command


def test_env_example_contains_placeholders_not_real_secrets() -> None:
    values = _load_env_example()

    assert values["POSTGRES_PASSWORD"] == "replace-with-local-password"
    assert values["CHAT_API_KEY"] == "replace-with-chat-provider-token"
    assert values["EMBEDDING_API_KEY"] == "replace-with-embedding-provider-token"
    assert values["CHAT_BASE_URL"] == "https://example.invalid/v1"
    assert values["EMBEDDING_BASE_URL"] == "https://example.invalid/v1"
    assert not values["CHAT_API_KEY"].startswith("sk-")
    assert not values["EMBEDDING_API_KEY"].startswith("sk-")


def test_runtime_docs_validate_local_knowledge_without_dependencies() -> None:
    runtime_docs = (ROOT / "docs" / "runtime.md").read_text(encoding="utf-8")

    assert "run --rm --no-deps" in runtime_docs
    assert "portfolio-rag-assistant runtime smoke" in runtime_docs


def _compose() -> dict[str, object]:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def _load_env_example() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", maxsplit=1)
        result[key] = value
    return result
