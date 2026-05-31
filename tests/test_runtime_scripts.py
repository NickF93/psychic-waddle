from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "runtime"

EXPECTED_PUBLIC_SCRIPTS = {
    "api-build.sh",
    "api-cleanup.sh",
    "api-down.sh",
    "api-setup.sh",
    "api-start.sh",
    "api-stop.sh",
    "letsencrypt-renew.sh",
    "letsencrypt-setup.sh",
    "llama-cpp-chat-cleanup.sh",
    "llama-cpp-chat-down.sh",
    "llama-cpp-chat-setup.sh",
    "llama-cpp-chat-start.sh",
    "llama-cpp-chat-stop.sh",
    "llama-cpp-embeddings-cleanup.sh",
    "llama-cpp-embeddings-down.sh",
    "llama-cpp-embeddings-setup.sh",
    "llama-cpp-embeddings-start.sh",
    "llama-cpp-embeddings-stop.sh",
    "ollama-chat-cleanup.sh",
    "ollama-chat-down.sh",
    "ollama-chat-setup.sh",
    "ollama-chat-start.sh",
    "ollama-chat-stop.sh",
    "ollama-embeddings-cleanup.sh",
    "ollama-embeddings-down.sh",
    "ollama-embeddings-setup.sh",
    "ollama-embeddings-start.sh",
    "ollama-embeddings-stop.sh",
    "postgres-cleanup.sh",
    "postgres-down.sh",
    "postgres-migrate.sh",
    "postgres-setup.sh",
    "postgres-start.sh",
    "postgres-stop.sh",
    "nginx-validate.sh",
    "public-build.sh",
    "public-cleanup.sh",
    "public-deploy.sh",
    "public-down.sh",
    "public-migrate.sh",
    "public-setup.sh",
    "public-smoke.sh",
    "public-start.sh",
    "public-stop.sh",
}


def test_runtime_script_suite_is_explicit() -> None:
    public_scripts = {
        path.name for path in SCRIPTS.glob("*.sh") if not path.name.startswith("_")
    }

    assert public_scripts == EXPECTED_PUBLIC_SCRIPTS
    assert (SCRIPTS / "_common.sh").is_file()


def test_runtime_scripts_are_executable_and_shell_valid() -> None:
    for path in SCRIPTS.glob("*.sh"):
        result = subprocess.run(
            ("sh", "-n", str(path)),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        if not path.name.startswith("_"):
            assert os.stat(path).st_mode & stat.S_IXUSR
            assert _read(path).startswith("#!/usr/bin/env sh\nset -eu\n")
            assert '. "$SCRIPT_DIR/_common.sh"' in _read(path)


def test_scripts_use_explicit_env_file_contract() -> None:
    common = _read(SCRIPTS / "_common.sh")

    assert 'ENV_FILE=${ENV_FILE:-"$ROOT_DIR/.env"}' in common
    assert 'docker compose --env-file "$ENV_FILE"' in common
    assert "RUNTIME_WAIT_TIMEOUT_SECONDS" in common
    assert "up --wait --wait-timeout" in common
    assert ".env.example" not in _all_script_text()


def test_scripts_do_not_use_legacy_runtime_config_names() -> None:
    script_text = _all_script_text()

    assert "DATABASE_URL" not in script_text
    assert "LLM_BACKEND" not in script_text
    assert "LLM_BASE_URL" not in script_text
    assert "LLM_API_KEY" not in script_text


def test_api_scripts_target_only_api_runtime_operations() -> None:
    assert "compose build api" in _script("api-build.sh")
    assert "compose build api" in _script("api-setup.sh")
    assert "compose_config" in _script("api-setup.sh")
    assert "compose_up_wait api" in _script("api-start.sh")
    assert "compose stop api" in _script("api-stop.sh")
    assert "remove_service api" in _script("api-down.sh")
    assert "remove_docker_image portfolio-rag-assistant:local" in _script(
        "api-cleanup.sh"
    )
    assert "migrate" not in _script("api-setup.sh")


def test_postgres_scripts_own_database_lifecycle_and_migration() -> None:
    assert "compose_up_wait db" in _script("postgres-setup.sh")
    assert "compose_up_wait db" in _script("postgres-start.sh")
    assert "compose stop db" in _script("postgres-stop.sh")
    assert "remove_service db" in _script("postgres-down.sh")
    assert "require_cleanup_flag --destroy-data" in _script("postgres-cleanup.sh")
    assert "remove_compose_volume postgres-data" in _script("postgres-cleanup.sh")
    assert "psql" in _script("postgres-migrate.sh")
    assert "--set ON_ERROR_STOP=1" in _script("postgres-migrate.sh")
    assert "/migrations/0001_knowledge_schema.sql" in _script("postgres-migrate.sh")


def test_migration_command_is_not_duplicated() -> None:
    migration_scripts = [
        path.name
        for path in SCRIPTS.glob("*.sh")
        if "psql" in _read(path) or "/migrations/" in _read(path)
    ]

    assert migration_scripts == ["postgres-migrate.sh"]


def test_ollama_scripts_use_profile_and_explicit_model_pull() -> None:
    assert "require_backend CHAT_BACKEND ollama" in _script("ollama-chat-setup.sh")
    assert "configured_value CHAT_MODEL" in _script("ollama-chat-setup.sh")
    assert "compose_profile_up_wait ollama ollama" in _script("ollama-chat-setup.sh")
    assert "ollama pull" in _script("ollama-chat-setup.sh")
    assert "require_backend EMBEDDING_BACKEND ollama" in _script(
        "ollama-embeddings-setup.sh"
    )
    assert "configured_value EMBEDDING_MODEL" in _script(
        "ollama-embeddings-setup.sh"
    )
    assert "compose_profile_up_wait ollama ollama" in _script(
        "ollama-embeddings-setup.sh"
    )
    assert "ollama pull" in _script("ollama-embeddings-setup.sh")

    for name in (
        "ollama-chat-start.sh",
        "ollama-chat-stop.sh",
        "ollama-chat-down.sh",
        "ollama-embeddings-start.sh",
        "ollama-embeddings-stop.sh",
        "ollama-embeddings-down.sh",
    ):
        assert "ollama" in _script(name)
    assert "compose_profile_up_wait ollama ollama" in _script("ollama-chat-start.sh")
    assert "compose_profile_up_wait ollama ollama" in _script(
        "ollama-embeddings-start.sh"
    )


def test_llama_cpp_scripts_keep_chat_and_embedding_services_separate() -> None:
    assert "require_backend CHAT_BACKEND llama-cpp" in _script(
        "llama-cpp-chat-setup.sh"
    )
    assert "LLAMA_CPP_CHAT_MODEL_PATH" in _script("llama-cpp-chat-setup.sh")
    assert "compose_profile_up_wait llama-cpp llama-cpp-chat" in _script(
        "llama-cpp-chat-setup.sh"
    )
    assert "compose_profile_up_wait llama-cpp llama-cpp-chat" in _script(
        "llama-cpp-chat-start.sh"
    )
    assert "require_backend EMBEDDING_BACKEND llama-cpp" in _script(
        "llama-cpp-embeddings-setup.sh"
    )
    assert "LLAMA_CPP_EMBEDDING_MODEL_PATH" in _script(
        "llama-cpp-embeddings-setup.sh"
    )
    assert "compose_profile_up_wait llama-cpp llama-cpp-embeddings" in _script(
        "llama-cpp-embeddings-setup.sh"
    )
    assert "compose_profile_up_wait llama-cpp llama-cpp-embeddings" in _script(
        "llama-cpp-embeddings-start.sh"
    )


def test_letsencrypt_scripts_use_explicit_tls_contract() -> None:
    setup = _script("letsencrypt-setup.sh")
    renew = _script("letsencrypt-renew.sh")

    assert "configured_value PUBLIC_SERVER_NAME" in setup
    assert "configured_value LETSENCRYPT_EMAIL" in setup
    assert "compose_profile_up_wait public nginx" in setup
    assert "compose_profile public run --rm certbot certonly" in setup
    assert "--webroot-path /var/www/certbot" in setup
    assert "--cert-name portfolio-rag-assistant" in setup
    assert '-d "$PUBLIC_SERVER_NAME"' in setup

    assert "configured_value PUBLIC_SERVER_NAME" in renew
    assert "configured_value LETSENCRYPT_EMAIL" in renew
    assert "compose_profile public-tls run --rm certbot renew" in renew
    assert "--webroot-path /var/www/certbot" in renew
    assert "--cert-name portfolio-rag-assistant" in renew
    assert "compose_profile public-tls exec nginx-tls nginx -s reload" in renew


def test_public_scripts_wrap_existing_runtime_authorities() -> None:
    assert '"$SCRIPT_DIR/nginx-validate.sh"' in _script("public-build.sh")
    assert '"$SCRIPT_DIR/api-build.sh"' in _script("public-build.sh")
    assert _script("public-migrate.sh").count("postgres-migrate.sh") == 1
    assert "psql" not in _script("public-migrate.sh")
    assert "/migrations/" not in _script("public-migrate.sh")
    assert '"$SCRIPT_DIR/public-build.sh"' in _script("public-deploy.sh")
    assert '"$SCRIPT_DIR/postgres-start.sh"' in _script("public-deploy.sh")
    assert '"$SCRIPT_DIR/public-migrate.sh"' in _script("public-deploy.sh")
    assert '"$SCRIPT_DIR/public-start.sh"' in _script("public-deploy.sh")
    assert '"$SCRIPT_DIR/public-smoke.sh"' in _script("public-deploy.sh")
    assert "letsencrypt-setup.sh" not in _script("public-deploy.sh")
    assert "letsencrypt-renew.sh" not in _script("public-deploy.sh")


def test_public_setup_requires_explicit_certificate_flag() -> None:
    setup = _script("public-setup.sh")

    assert "usage: public-setup.sh [--issue-certificate]" in setup
    assert '[ "$1" = "--issue-certificate" ]' in setup
    assert "ISSUE_CERTIFICATE=true" in setup
    assert 'if [ "$ISSUE_CERTIFICATE" = true ]; then' in setup
    assert '"$SCRIPT_DIR/letsencrypt-setup.sh"' in setup
    assert "compose_profile public stop nginx" in setup
    assert "certificate issuance skipped" in setup


def test_public_start_stops_bootstrap_edge_before_tls_runtime() -> None:
    start = _script("public-start.sh")

    assert "compose_profile public stop nginx" in start
    assert "compose_profile_up_wait public-tls nginx-tls" in start
    assert start.index("compose_profile public stop nginx") < start.index(
        "compose_profile_up_wait public-tls nginx-tls"
    )


def test_public_scripts_dispatch_configured_local_providers() -> None:
    for script_name, verb in (
        ("public-setup.sh", "setup"),
        ("public-start.sh", "start"),
        ("public-stop.sh", "stop"),
        ("public-down.sh", "down"),
    ):
        script = _script(script_name)
        assert "env_value CHAT_BACKEND" in script
        assert "env_value EMBEDDING_BACKEND" in script
        assert f"ollama-chat-{verb}.sh" in script
        assert f"ollama-embeddings-{verb}.sh" in script
        assert f"llama-cpp-chat-{verb}.sh" in script
        assert f"llama-cpp-embeddings-{verb}.sh" in script
        assert "openai-compatible" in script
        assert "unsupported CHAT_BACKEND" in script
        assert "unsupported EMBEDDING_BACKEND" in script


def test_public_cleanup_preserves_data_model_and_certificate_volumes() -> None:
    cleanup = _script("public-cleanup.sh")

    assert '"$SCRIPT_DIR/public-down.sh"' in cleanup
    assert "remove_docker_image portfolio-rag-assistant:local" in cleanup
    assert "postgres-cleanup.sh" not in cleanup
    assert "ollama-chat-cleanup.sh" not in cleanup
    assert "ollama-embeddings-cleanup.sh" not in cleanup
    assert "Let's Encrypt" in cleanup
    assert "preserved" in cleanup


def test_public_smoke_supports_local_default_and_public_override() -> None:
    smoke = _script("public-smoke.sh")

    assert "PUBLIC_SMOKE_BASE_URL=${PUBLIC_SMOKE_BASE_URL:-http://127.0.0.1:8080}" in smoke
    assert "PUBLIC_SMOKE_ORIGIN=${PUBLIC_SMOKE_ORIGIN:-https://pigreco.xyz}" in smoke
    assert "curl -fsS -X OPTIONS" in smoke
    assert "access-control-request-method: POST" in smoke
    assert "/api/assistant/health" in smoke
    assert "/api/assistant/ready" in smoke
    assert "/api/assistant/chat" in smoke
    assert '{"question":"Where did Niccolo work?","language":"en"}' in smoke
    assert '"answerable", "not_answerable", "needs_clarification"' in smoke


def test_nginx_validate_checks_both_public_edge_configs() -> None:
    validate = _script("nginx-validate.sh")

    assert "compose_profile public config >/dev/null" in validate
    assert "compose_profile public-tls config >/dev/null" in validate
    assert "deploy/nginx/nginx.conf" in validate
    assert "deploy/nginx/nginx-tls.conf" in validate
    assert "proxy_pass http://api:8000/chat?;" in validate
    assert "proxy_pass http://api:8000/health?;" in validate
    assert "proxy_pass http://api:8000/ready?;" in validate
    assert "listen 443 ssl;" in validate


def test_cleanup_scripts_are_bounded() -> None:
    script_text = _all_script_text()

    assert "down --volumes" not in script_text
    assert "down -v" not in script_text
    assert "rm -rf" not in script_text
    assert "remove_compose_volume letsencrypt-certs" not in script_text
    assert "remove_compose_volume letsencrypt-work" not in script_text
    assert "remove_compose_volume acme-challenges" not in script_text
    assert "require_cleanup_flag --destroy-data" in _script("postgres-cleanup.sh")
    assert "require_cleanup_flag --destroy-models" in _script(
        "ollama-chat-cleanup.sh"
    )
    assert "require_cleanup_flag --destroy-models" in _script(
        "ollama-embeddings-cleanup.sh"
    )
    assert "remove_compose_volume" not in _script("llama-cpp-chat-cleanup.sh")
    assert "remove_compose_volume" not in _script(
        "llama-cpp-embeddings-cleanup.sh"
    )


def _script(name: str) -> str:
    return _read(SCRIPTS / name)


def _all_script_text() -> str:
    return "\n".join(_read(path) for path in sorted(SCRIPTS.glob("*.sh")))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
