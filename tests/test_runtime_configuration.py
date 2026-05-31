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
    assert services["nginx-tls"]["image"].startswith(
        "nginx:1.27.5-alpine@sha256:"
    )
    assert services["certbot"]["image"].startswith(
        "certbot/certbot:latest@sha256:"
    )
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


def test_compose_public_bootstrap_edge_is_profile_gated_and_http_only() -> None:
    nginx = _compose()["services"]["nginx"]

    assert nginx["profiles"] == ["public"]
    assert nginx["depends_on"] == {"api": {"condition": "service_healthy"}}
    assert nginx["ports"] == [
        "${PUBLIC_HTTP_BIND_ADDRESS:?missing PUBLIC_HTTP_BIND_ADDRESS}:${PUBLIC_HTTP_PORT:?missing PUBLIC_HTTP_PORT}:80"
    ]
    assert "443" not in "\n".join(nginx["ports"])
    assert nginx["volumes"] == [
        "./deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro",
        "acme-challenges:/var/www/certbot:ro",
    ]
    assert nginx["networks"] == ["runtime"]
    assert "/api/assistant/health" in nginx["healthcheck"]["test"][-1]


def test_compose_public_tls_edge_is_profile_gated_and_owns_443() -> None:
    services = _compose()["services"]
    nginx_tls = services["nginx-tls"]

    assert nginx_tls["profiles"] == ["public-tls"]
    assert nginx_tls["depends_on"] == {"api": {"condition": "service_healthy"}}
    assert nginx_tls["ports"] == [
        "${PUBLIC_HTTP_BIND_ADDRESS:?missing PUBLIC_HTTP_BIND_ADDRESS}:${PUBLIC_HTTP_PORT:?missing PUBLIC_HTTP_PORT}:80",
        "${PUBLIC_HTTPS_BIND_ADDRESS:?missing PUBLIC_HTTPS_BIND_ADDRESS}:${PUBLIC_HTTPS_PORT:?missing PUBLIC_HTTPS_PORT}:443",
    ]
    assert nginx_tls["volumes"] == [
        "./deploy/nginx/nginx-tls.conf:/etc/nginx/nginx.conf:ro",
        "acme-challenges:/var/www/certbot:ro",
        "letsencrypt-certs:/etc/letsencrypt:ro",
    ]
    assert nginx_tls["healthcheck"]["test"] == ["CMD-SHELL", "nginx -t"]

    services_with_443 = [
        name
        for name, service in services.items()
        if "443" in "\n".join(str(port) for port in service.get("ports", ()))
    ]

    assert services_with_443 == ["nginx-tls"]


def test_compose_certbot_uses_bounded_certificate_volumes() -> None:
    compose = _compose()
    certbot = compose["services"]["certbot"]

    assert certbot["profiles"] == ["public", "public-tls"]
    assert certbot["volumes"] == [
        "letsencrypt-certs:/etc/letsencrypt",
        "letsencrypt-work:/var/lib/letsencrypt",
        "acme-challenges:/var/www/certbot",
    ]
    assert set(compose["volumes"]) >= {
        "letsencrypt-certs",
        "letsencrypt-work",
        "acme-challenges",
    }


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
            ("public-tls", ("--profile", "public-tls")),
        )
    }

    assert "api" in rendered["default"]["services"]
    assert "db" in rendered["default"]["services"]
    assert "llama-cpp-chat" in rendered["llama-cpp"]["services"]
    assert "llama-cpp-embeddings" in rendered["llama-cpp"]["services"]
    assert "ollama" in rendered["ollama"]["services"]
    assert "nginx" in rendered["public"]["services"]
    assert "certbot" in rendered["public"]["services"]
    assert "nginx-tls" in rendered["public-tls"]["services"]
    assert "certbot" in rendered["public-tls"]["services"]
    assert rendered["public"]["services"]["nginx"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 80,
            "published": "18080",
            "protocol": "tcp",
        }
    ]
    assert rendered["public-tls"]["services"]["nginx-tls"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 80,
            "published": "18080",
            "protocol": "tcp",
        },
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 443,
            "published": "18443",
            "protocol": "tcp",
        },
    ]


def test_public_edge_env_vars_are_required(tmp_path: Path) -> None:
    _require_docker_compose()
    env_without_public_edge = "\n".join(
        line
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if not line.startswith(
            (
                "PUBLIC_HTTP_BIND_ADDRESS=",
                "PUBLIC_HTTP_PORT=",
                "PUBLIC_HTTPS_BIND_ADDRESS=",
                "PUBLIC_HTTPS_PORT=",
            )
        )
    )
    env_path = tmp_path / "missing-public-edge.env"
    env_path.write_text(f"{env_without_public_edge}\n", encoding="utf-8")

    result = subprocess.run(
        (
            "docker",
            "compose",
            "--env-file",
            str(env_path),
            "--profile",
            "public",
            "config",
        ),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "PUBLIC_HTTP_BIND_ADDRESS" in f"{result.stdout}\n{result.stderr}"


def test_env_example_contains_placeholders_not_real_secrets() -> None:
    values = _load_env_example()

    assert values["PUBLIC_HTTP_BIND_ADDRESS"] == "127.0.0.1"
    assert values["PUBLIC_HTTP_PORT"] == "18080"
    assert values["PUBLIC_HTTPS_BIND_ADDRESS"] == "127.0.0.1"
    assert values["PUBLIC_HTTPS_PORT"] == "18443"
    assert values["PUBLIC_SERVER_NAME"] == "vps.madnick.ovh"
    assert values["LETSENCRYPT_EMAIL"] == "replace-with-letsencrypt-email"
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
    assert "knowledge/` is ignored by Git" in runtime_docs


def test_local_deployment_knowledge_is_git_ignored() -> None:
    result = subprocess.run(
        ("git", "check-ignore", "--quiet", "knowledge/profile.json"),
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0


def test_public_edge_routes_are_mapped_to_internal_api() -> None:
    nginx = _nginx_config()
    nginx_tls = _nginx_config("nginx-tls.conf")

    for config in (nginx, nginx_tls):
        assert "location = /api/assistant/chat" in config
        assert "proxy_pass http://api:8000/chat?;" in config
        assert "location = /api/assistant/health" in config
        assert "proxy_pass http://api:8000/health?;" in config
        assert "location = /api/assistant/ready" in config
        assert "proxy_pass http://api:8000/ready?;" in config


def test_public_edge_cors_allows_only_portfolio_origins() -> None:
    cors_maps = (
        _nginx_map("$assistant_cors_origin"),
        _nginx_map("$assistant_cors_origin", "nginx-tls.conf"),
    )

    for cors_map in cors_maps:
        assert sorted(re.findall(r'"(https://[^"]+)"', cors_map)) == [
            "https://pigreco.xyz",
            "https://www.pigreco.xyz",
        ]
        assert 'default "";' in cors_map

    assert "Access-Control-Allow-Origin *" not in _nginx_config()
    assert "Access-Control-Allow-Origin *" not in _nginx_config("nginx-tls.conf")


def test_public_edge_serves_acme_challenges_without_logging_identity() -> None:
    for config in (_nginx_config(), _nginx_config("nginx-tls.conf")):
        assert "location ^~ /.well-known/acme-challenge/" in config
        assert "root /var/www/certbot;" in config
        assert "try_files $uri =404;" in config
        assert "access_log off;" in config


def test_public_tls_edge_uses_real_certificate_volume_and_redirects_http() -> None:
    nginx_tls = _nginx_config("nginx-tls.conf")

    assert "listen 443 ssl;" in nginx_tls
    assert "ssl_certificate /etc/letsencrypt/live/portfolio-rag-assistant/fullchain.pem;" in nginx_tls
    assert "ssl_certificate_key /etc/letsencrypt/live/portfolio-rag-assistant/privkey.pem;" in nginx_tls
    assert "return 308 https://vps.madnick.ovh$uri;" in nginx_tls
    assert "return 308 https://$host" not in nginx_tls
    assert "$request_uri" not in nginx_tls
    assert "self-signed" not in nginx_tls
    assert "snakeoil" not in nginx_tls


def test_public_edge_privacy_contract_bounds_operational_metadata() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    deployment = (ROOT / "docs" / "public-deployment.md").read_text(
        encoding="utf-8"
    )

    for document in (agents, architecture, deployment):
        normalized_document = " ".join(document.split())
        assert "redacted operational" in normalized_document
        assert "raw question" in normalized_document
        assert "answer text" in normalized_document

    assert "volatile IP-derived key" in " ".join(agents.split())
    assert "IP-derived rate-limit key only in volatile" in " ".join(
        architecture.split()
    )
    assert "IP-derived key in volatile Nginx memory" in " ".join(deployment.split())
    assert "must not be logged, exported, persisted, forwarded" in " ".join(
        deployment.split()
    )


def test_public_edge_logging_is_redacted() -> None:
    log_formats = (_nginx_log_format(), _nginx_log_format("nginx-tls.conf"))

    for log_format in log_formats:
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
    for config in (_nginx_config(), _nginx_config("nginx-tls.conf")):
        assert "X-Forwarded-For" not in config
        assert "X-Real-IP" not in config


def test_public_edge_rate_limit_and_bounds_are_configured() -> None:
    deployment = (ROOT / "docs" / "public-deployment.md").read_text(
        encoding="utf-8"
    )

    for config in (_nginx_config(), _nginx_config("nginx-tls.conf")):
        assert (
            "limit_req_zone $binary_remote_addr zone=assistant_chat:10m rate=20r/m;"
            in config
        )
        assert "limit_req zone=assistant_chat burst=40 nodelay;" in config
        assert "client_max_body_size 4k;" in config
        assert "proxy_connect_timeout 5s;" in config
        assert "proxy_send_timeout 90s;" in config
        assert "proxy_read_timeout 120s;" in config

    normalized_deployment = " ".join(deployment.split())
    assert "volatile Nginx memory" in normalized_deployment
    assert "must not be logged, exported, persisted, forwarded" in normalized_deployment


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


def _nginx_config(filename: str = "nginx.conf") -> str:
    return (ROOT / "deploy" / "nginx" / filename).read_text(encoding="utf-8")


def _nginx_map(name: str, filename: str = "nginx.conf") -> str:
    match = re.search(
        rf"map \$http_origin {re.escape(name)} \{{(?P<body>.*?)\n    \}}",
        _nginx_config(filename),
        re.DOTALL,
    )

    assert match is not None
    return match.group("body")


def _nginx_log_format(filename: str = "nginx.conf") -> str:
    match = re.search(
        r"log_format assistant_redacted(?P<body>.*?);",
        _nginx_config(filename),
        re.DOTALL,
    )

    assert match is not None
    return match.group("body")
