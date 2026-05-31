from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_build_system_dependencies_are_exactly_pinned() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = pyproject["build-system"]["requires"]

    assert requirements == ["setuptools==80.9.0"]
    for requirement in requirements:
        assert "==" in requirement
        assert ">=" not in requirement
        assert "<" not in requirement
        assert "~=" not in requirement
        assert "!=" not in requirement


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

    assert services["nginx"]["image"].startswith("nginx:1.27.5-alpine@sha256:")
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


def test_compose_public_edge_is_profile_gated_and_http_only() -> None:
    nginx = _compose()["services"]["nginx"]

    assert nginx["profiles"] == ["public"]
    assert nginx["depends_on"] == {"api": {"condition": "service_healthy"}}
    assert nginx["ports"] == [
        "${PUBLIC_HTTP_BIND_ADDRESS:-127.0.0.1}:${PUBLIC_HTTP_PORT:-8080}:80"
    ]
    assert "443" not in "\n".join(nginx["ports"])
    assert nginx["volumes"] == ["./deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro"]
    assert nginx["networks"] == ["runtime"]
    assert "/api/assistant/health" in nginx["healthcheck"]["test"][-1]


def test_compose_keeps_healthcheck_as_liveness_only() -> None:
    healthcheck = _compose()["services"]["api"]["healthcheck"]

    assert "/health" in healthcheck["test"][-1]
    assert "/ready" not in healthcheck["test"][-1]


def test_compose_local_llms_are_profile_gated() -> None:
    services = _compose()["services"]

    assert services["ollama"]["profiles"] == ["ollama"]
    assert services["llama-cpp-chat"]["profiles"] == ["llama-cpp"]
    assert services["llama-cpp-embeddings"]["profiles"] == ["llama-cpp"]


def test_compose_local_llms_have_readiness_healthchecks() -> None:
    services = _compose()["services"]

    assert services["ollama"]["healthcheck"]["test"] == [
        "CMD",
        "ollama",
        "list",
    ]
    for service_name in ("llama-cpp-chat", "llama-cpp-embeddings"):
        healthcheck = services[service_name]["healthcheck"]
        assert healthcheck["test"] == [
            "CMD",
            "curl",
            "-fsS",
            "http://127.0.0.1:8080/health",
        ]
        assert healthcheck["retries"] >= 12


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


def test_docker_compose_config_renders_supported_profiles() -> None:
    _require_docker_compose()

    rendered = {
        name: _render_compose_config(args)
        for name, args in (
            ("default", ()),
            ("llama-cpp", ("--profile", "llama-cpp")),
            ("ollama", ("--profile", "ollama")),
            ("public", ("--profile", "public")),
        )
    }

    assert "api" in rendered["default"]["services"]
    assert "db" in rendered["default"]["services"]
    assert "llama-cpp-chat" in rendered["llama-cpp"]["services"]
    assert "llama-cpp-embeddings" in rendered["llama-cpp"]["services"]
    assert "ollama" in rendered["ollama"]["services"]
    assert "nginx" in rendered["public"]["services"]
    assert rendered["public"]["services"]["nginx"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 80,
            "published": "8080",
            "protocol": "tcp",
        }
    ]


def test_env_example_contains_placeholders_not_real_secrets() -> None:
    values = _load_env_example()

    assert values["PUBLIC_HTTP_BIND_ADDRESS"] == "127.0.0.1"
    assert values["PUBLIC_HTTP_PORT"] == "8080"
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


def test_public_edge_routes_are_mapped_to_internal_api() -> None:
    nginx = _nginx_config()

    assert "location = /api/assistant/chat" in nginx
    assert "proxy_pass http://api:8000/chat?;" in nginx
    assert "location = /api/assistant/health" in nginx
    assert "proxy_pass http://api:8000/health?;" in nginx
    assert "location = /api/assistant/ready" in nginx
    assert "proxy_pass http://api:8000/ready?;" in nginx


def test_public_edge_cors_allows_only_portfolio_origins() -> None:
    cors_map = _nginx_map("$assistant_cors_origin")

    assert sorted(re.findall(r'"(https://[^"]+)"', cors_map)) == [
        "https://pigreco.xyz",
        "https://www.pigreco.xyz",
    ]
    assert 'default "";' in cors_map
    assert "Access-Control-Allow-Origin *" not in _nginx_config()


def test_public_edge_logging_is_redacted() -> None:
    log_format = _nginx_log_format()

    assert "$request_method" in log_format
    assert "$uri" in log_format
    assert "$status" in log_format
    assert "$assistant_cors_origin" in log_format

    for forbidden_field in (
        "$remote_addr",
        "$http_user_agent",
        "$http_cookie",
        "$request_body",
        "$request_uri",
        "$args",
    ):
        assert forbidden_field not in log_format


def test_public_edge_does_not_forward_visitor_identity_headers() -> None:
    nginx = _nginx_config()

    assert "X-Forwarded-For" not in nginx
    assert "X-Real-IP" not in nginx


def test_public_edge_rate_limit_and_bounds_are_configured() -> None:
    nginx = _nginx_config()

    assert (
        "limit_req_zone $binary_remote_addr zone=assistant_chat:10m rate=20r/m;"
        in nginx
    )
    assert "limit_req zone=assistant_chat burst=40 nodelay;" in nginx
    assert "client_max_body_size 4k;" in nginx
    assert "proxy_connect_timeout 5s;" in nginx
    assert "proxy_send_timeout 90s;" in nginx
    assert "proxy_read_timeout 120s;" in nginx


def _compose() -> dict[str, object]:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def _render_compose_config(profile_args: tuple[str, ...]) -> dict[str, object]:
    result = subprocess.run(
        (
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            *profile_args,
            "config",
        ),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return yaml.safe_load(result.stdout)


def _require_docker_compose() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")

    result = subprocess.run(
        ("docker", "compose", "version"),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("docker compose is not available")


def _load_env_example() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", maxsplit=1)
        result[key] = value
    return result


def _nginx_config() -> str:
    return (ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")


def _nginx_map(name: str) -> str:
    match = re.search(
        rf"map \$http_origin {re.escape(name)} \{{(?P<body>.*?)\n    \}}",
        _nginx_config(),
        re.DOTALL,
    )

    assert match is not None
    return match.group("body")


def _nginx_log_format() -> str:
    match = re.search(
        r"log_format assistant_redacted(?P<body>.*?);",
        _nginx_config(),
        re.DOTALL,
    )

    assert match is not None
    return match.group("body")
