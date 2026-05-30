from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_starts_the_public_api_entrypoint() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER app" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "portfolio_rag_assistant.api.main:app" in dockerfile
    assert "--host\", \"0.0.0.0" in dockerfile
    assert ".env" not in dockerfile


def test_compose_uses_pgvector_pg17_and_private_runtime_network() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "image: pgvector/pgvector:0.8.2-pg17" in compose
    assert "postgres-data:/var/lib/postgresql/data" in compose
    assert "./migrations:/migrations:ro" in compose
    assert "driver: bridge" in compose


def test_compose_keeps_api_port_localhost_by_default() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert '"${API_BIND_ADDRESS:-127.0.0.1}:${API_PORT:-8000}:8000"' in compose


def test_compose_local_llms_are_profile_gated() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "image: ollama/ollama" in compose
    assert "image: ghcr.io/ggml-org/llama.cpp:server" in compose
    assert "profiles:\n      - ollama" in compose
    assert "profiles:\n      - llama-cpp" in compose


def test_env_example_contains_placeholders_not_real_secrets() -> None:
    values = _load_env_example()

    assert values["POSTGRES_PASSWORD"] == "replace-with-local-password"
    assert values["LLM_API_KEY"] == "replace-with-provider-token"
    assert values["LLM_BASE_URL"] == "https://example.invalid/v1"
    assert not values["LLM_API_KEY"].startswith("sk-")


def _load_env_example() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", maxsplit=1)
        result[key] = value
    return result
