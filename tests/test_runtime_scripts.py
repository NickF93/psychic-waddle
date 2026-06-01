from __future__ import annotations

import json
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
    "public-certbot-install-timer.sh",
    "public-certbot-status.sh",
    "public-certbot-test-renewal.sh",
    "public-build.sh",
    "public-cleanup.sh",
    "public-deploy.sh",
    "public-down.sh",
    "public-load-knowledge.sh",
    "public-migrate.sh",
    "public-reset-and-setup.sh",
    "public-setup.sh",
    "public-smoke.sh",
    "public-start.sh",
    "public-stop.sh",
    "public-upgrade.sh",
    "public-validate-env.sh",
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
    assert "compose_provider_run()" in common
    assert "compose --profile ollama --profile llama-cpp run --rm" in common
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
    assert "for migration in /migrations/*.sql" in _script("postgres-migrate.sh")
    assert "schema_migrations" in _script("postgres-migrate.sh")
    assert "checksum_sha256" in _script("postgres-migrate.sh")
    assert "sha256sum" in _script("postgres-migrate.sh")
    assert "BEGIN;" in _script("postgres-migrate.sh")
    assert "COMMIT;" in _script("postgres-migrate.sh")
    assert "refusing to guess applied migrations" in _script("postgres-migrate.sh")
    old_replay_command = (
        'psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" '
        '-d "$POSTGRES_DB" -f "$migration"'
    )
    assert old_replay_command not in _script("postgres-migrate.sh")


def test_postgres_migration_script_tracks_applied_files_once() -> None:
    migrate = _script("postgres-migrate.sh")

    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in migrate
    assert "SELECT checksum_sha256" in migrate
    assert "migration already applied" in migrate
    assert "migration checksum mismatch" in migrate
    assert "INSERT INTO schema_migrations" in migrate
    assert migrate.index("\\i $migration") < migrate.index(
        "INSERT INTO schema_migrations"
    )


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
    assert "configured_value PUBLIC_HTTP_BIND_ADDRESS" in setup
    assert "configured_value PUBLIC_HTTP_PORT" in setup
    assert 'PUBLIC_HTTP_BIND_ADDRESS" = "0.0.0.0"' in setup
    assert 'PUBLIC_HTTP_PORT" = "80"' in setup
    assert "compose_profile_up_wait public nginx" in setup
    assert "compose_profile public run --rm certbot certonly" in setup
    assert "--webroot-path /var/www/certbot" in setup
    assert "--cert-name portfolio-rag-assistant" in setup
    assert '-d "$PUBLIC_SERVER_NAME"' in setup

    assert "configured_value PUBLIC_SERVER_NAME" in renew
    assert "configured_value LETSENCRYPT_EMAIL" in renew
    assert "compose_profile public-tls run --rm certbot renew" in renew
    assert "--dry-run" in renew
    assert "--webroot-path /var/www/certbot" in renew
    assert "--cert-name portfolio-rag-assistant" in renew
    assert "--deploy-hook" in renew
    assert "MARKER_MOUNT=/var/lib/portfolio-rag-assistant-renewal" in renew
    assert "no certificates renewed; nginx reload skipped" in renew
    assert "compose_profile public-tls exec nginx-tls nginx -t" in renew
    assert "compose_profile public-tls exec nginx-tls nginx -s reload" in renew


def test_public_certbot_operator_scripts_are_bounded() -> None:
    status = _script("public-certbot-status.sh")
    test_renewal = _script("public-certbot-test-renewal.sh")
    timer = _script("public-certbot-install-timer.sh")

    assert "compose_profile public-tls run --rm certbot certificates" in status
    assert "--cert-name portfolio-rag-assistant" in status
    assert '"$SCRIPT_DIR/letsencrypt-renew.sh" --dry-run' in test_renewal
    assert "usage: public-certbot-install-timer.sh [--dry-run]" in timer
    assert "portfolio-rag-assistant-letsencrypt-renew.service" in timer
    assert "portfolio-rag-assistant-letsencrypt-renew.timer" in timer
    assert "ExecStart=$ROOT_DIR/scripts/runtime/letsencrypt-renew.sh" in timer
    assert "Environment=ENV_FILE=$ENV_FILE" in timer
    assert "OnCalendar=*-*-* 03,15:17:00" in timer
    assert "RandomizedDelaySec=1h" in timer
    assert "systemctl enable --now" in timer


def test_public_certbot_timer_dry_run_does_not_require_systemctl(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PUBLIC_SERVER_NAME=vps.madnick.ovh\n"
        "LETSENCRYPT_EMAIL=ops@example.invalid\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["ENV_FILE"] = str(env_file)

    result = subprocess.run(
        (str(SCRIPTS / "public-certbot-install-timer.sh"), "--dry-run"),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "would install /etc/systemd/system/portfolio-rag-assistant-letsencrypt-renew.service" in result.stdout
    assert "ExecStart=" in result.stdout
    assert "letsencrypt-renew.sh" in result.stdout
    assert "portfolio-rag-assistant-letsencrypt-renew.timer" in result.stdout


def test_letsencrypt_setup_rejects_non_public_http_config(tmp_path: Path) -> None:
    cases = (
        (
            "PUBLIC_HTTP_BIND_ADDRESS=127.0.0.1\nPUBLIC_HTTP_PORT=80\n",
            "PUBLIC_HTTP_BIND_ADDRESS must be 0.0.0.0",
        ),
        (
            "PUBLIC_HTTP_BIND_ADDRESS=0.0.0.0\nPUBLIC_HTTP_PORT=18080\n",
            "PUBLIC_HTTP_PORT must be 80",
        ),
    )

    for index, (public_config, expected_error) in enumerate(cases):
        env_file = tmp_path / f"letsencrypt-{index}.env"
        env_file.write_text(
            "PUBLIC_SERVER_NAME=vps.madnick.ovh\n"
            "LETSENCRYPT_EMAIL=ops@example.invalid\n"
            f"{public_config}",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["ENV_FILE"] = str(env_file)

        result = subprocess.run(
            (str(SCRIPTS / "letsencrypt-setup.sh"),),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert result.returncode != 0
        assert expected_error in result.stderr


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


def test_public_env_validator_checks_explicit_public_runtime_contract() -> None:
    validate = _script("public-validate-env.sh")

    for key in (
        "API_BIND_ADDRESS",
        "API_PORT",
        "PUBLIC_HTTP_BIND_ADDRESS",
        "PUBLIC_HTTP_PORT",
        "PUBLIC_HTTPS_BIND_ADDRESS",
        "PUBLIC_HTTPS_PORT",
        "PUBLIC_SERVER_NAME",
        "LETSENCRYPT_EMAIL",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "CHAT_BACKEND",
        "CHAT_BASE_URL",
        "CHAT_MODEL",
        "EMBEDDING_BACKEND",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        "RETRIEVAL_TOP_K",
        "RETRIEVAL_MIN_SCORE",
        "QUESTION_COLLECTION_ENABLED",
    ):
        assert key in validate

    assert "API_BIND_ADDRESS must be 127.0.0.1" in validate
    assert "require_backend_value CHAT_BACKEND" in validate
    assert "require_backend_value EMBEDDING_BACKEND" in validate
    assert "configured_value CHAT_API_KEY" in validate
    assert "configured_value EMBEDDING_API_KEY" in validate
    assert "require_llama_model_file LLAMA_CPP_CHAT_MODEL_PATH" in validate
    assert "require_llama_model_file LLAMA_CPP_EMBEDDING_MODEL_PATH" in validate
    assert "require_boolean QUESTION_COLLECTION_ENABLED" in validate
    assert "compose config >/dev/null" in validate
    assert "compose_profile public config >/dev/null" in validate
    assert "compose_profile public-tls config >/dev/null" in validate


def test_public_load_knowledge_delegates_to_existing_cli_commands() -> None:
    load = _script("public-load-knowledge.sh")

    assert 'PUBLIC_KNOWLEDGE_FILE:-"$ROOT_DIR/knowledge/profile.json"' in load
    assert 'PUBLIC_KNOWLEDGE_FILE must point inside $ROOT_DIR/knowledge' in load
    assert "--volume \"$ROOT_DIR/knowledge:/knowledge:ro\"" in load
    assert "portfolio-rag-assistant knowledge validate" in load
    assert "portfolio-rag-assistant knowledge ingest" in load
    assert "portfolio-rag-assistant knowledge index-embeddings" in load
    assert "compose_profile ollama run --rm api" in load
    assert "compose_profile llama-cpp run --rm api" in load
    assert "unsupported EMBEDDING_BACKEND" in load
    assert "psql" not in load
    assert "/migrations/" not in load


def test_public_setup_requires_explicit_certificate_flag() -> None:
    setup = _script("public-setup.sh")

    assert "usage: public-setup.sh [--issue-certificate]" in setup
    assert '[ "$1" = "--issue-certificate" ]' in setup
    assert "ISSUE_CERTIFICATE=true" in setup
    assert 'if [ "$ISSUE_CERTIFICATE" = true ]; then' in setup
    assert '"$SCRIPT_DIR/letsencrypt-setup.sh"' in setup
    assert "compose_profile public stop nginx" in setup
    assert "certificate issuance skipped" in setup


def test_public_reset_requires_destructive_flags() -> None:
    reset = _script("public-reset-and-setup.sh")

    assert "usage: public-reset-and-setup.sh (--destroy-db|--destroy-models|--destroy-certs)" in reset
    assert "reset requires at least one explicit destructive flag" in reset
    assert "DESTROY_DB=false" in reset
    assert "DESTROY_MODELS=false" in reset
    assert "DESTROY_CERTS=false" in reset
    assert '"$SCRIPT_DIR/public-cleanup.sh"' in reset
    assert '"$SCRIPT_DIR/postgres-cleanup.sh" --destroy-data' in reset
    assert '"$SCRIPT_DIR/ollama-chat-cleanup.sh" --destroy-models' in reset
    assert "remove_compose_volume letsencrypt-certs" in reset
    assert "remove_compose_volume letsencrypt-work" in reset
    assert "remove_compose_volume acme-challenges" in reset
    assert '"$SCRIPT_DIR/public-validate-env.sh"' in reset
    assert '"$SCRIPT_DIR/public-setup.sh"' in reset
    assert '"$SCRIPT_DIR/public-load-knowledge.sh"' in reset
    assert "compose_provider_run api portfolio-rag-assistant runtime smoke" in reset
    assert '"$SCRIPT_DIR/public-smoke.sh"' in reset


def test_public_reset_fails_before_docker_without_destructive_flags() -> None:
    result = subprocess.run(
        (str(SCRIPTS / "public-reset-and-setup.sh"),),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "reset requires at least one explicit destructive flag" in result.stderr


def test_public_upgrade_preserves_runtime_state_and_refreshes_knowledge() -> None:
    upgrade = _script("public-upgrade.sh")

    assert "usage: public-upgrade.sh [--skip-knowledge-refresh] [--tls-runtime]" in upgrade
    assert "SKIP_KNOWLEDGE_REFRESH=false" in upgrade
    assert "TLS_RUNTIME=false" in upgrade
    assert '"$SCRIPT_DIR/public-validate-env.sh"' in upgrade
    assert '"$SCRIPT_DIR/public-setup.sh"' in upgrade
    assert '"$SCRIPT_DIR/public-load-knowledge.sh"' in upgrade
    assert "knowledge refresh skipped" in upgrade
    assert '"$SCRIPT_DIR/public-start.sh"' in upgrade
    assert "compose_profile_up_wait public nginx" in upgrade
    assert "compose_provider_run api portfolio-rag-assistant runtime smoke" in upgrade
    assert '"$SCRIPT_DIR/public-smoke.sh"' in upgrade
    assert "cleanup.sh" not in upgrade
    assert "remove_compose_volume" not in upgrade
    assert "--destroy-data" not in upgrade
    assert "--destroy-models" not in upgrade
    assert "--destroy-certs" not in upgrade


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

    assert "PUBLIC_SMOKE_BASE_URL=${PUBLIC_SMOKE_BASE_URL:-http://127.0.0.1:18080}" in smoke
    assert "PUBLIC_SMOKE_ALLOWED_ORIGIN=https://pigreco.xyz" in smoke
    assert "PUBLIC_SMOKE_ALLOWED_WWW_ORIGIN=https://www.pigreco.xyz" in smoke
    assert "PUBLIC_SMOKE_REJECTED_ORIGIN=https://example.invalid" in smoke
    assert "assert_cors_preflight_allowed" in smoke
    assert "assert_cors_preflight_rejected" in smoke
    assert "access-control-allow-origin" in smoke
    assert "access-control-request-method: POST" in smoke
    assert "/api/assistant/health" in smoke
    assert "/api/assistant/ready" in smoke
    assert "/api/assistant/chat" in smoke
    assert '{"question":"Where did Niccolo work?","language":"en"}' in smoke
    assert "PUBLIC_SMOKE_CHECK_QUESTION_COLLECTION" in smoke
    assert '{"question":"What is Niccolo favorite pizza topping?","language":"en"}' in smoke
    assert '{"code": "question_recorded"}' in smoke
    assert '"answerable", "not_answerable", "needs_clarification"' in smoke
    assert "PUBLIC_DIRECT_API_PROBE_URL" in smoke
    assert "2??) fail" in smoke
    assert "direct API probe skipped" in smoke


def test_public_smoke_executes_public_checks_with_fake_curl(tmp_path: Path) -> None:
    fake_curl_log = tmp_path / "curl.log"
    _write_fake_curl(tmp_path)
    env = _fake_curl_env(tmp_path, fake_curl_log)
    env["PUBLIC_DIRECT_API_PROBE_URL"] = "http://public-api-closed:8000/health"

    result = subprocess.run(
        (str(SCRIPTS / "public-smoke.sh"),),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "cors preflight passed: https://pigreco.xyz" in result.stdout
    assert "cors preflight passed: https://www.pigreco.xyz" in result.stdout
    assert "unexpected origin rejected: https://example.invalid" in result.stdout
    assert "direct API probe passed: http://public-api-closed:8000/health returned 000" in result.stdout
    assert "public smoke passed: http://127.0.0.1:18080" in result.stdout

    calls = [json.loads(line) for line in fake_curl_log.read_text().splitlines()]
    assert any("origin: https://pigreco.xyz" in call for call in calls)
    assert any("origin: https://www.pigreco.xyz" in call for call in calls)
    assert any("origin: https://example.invalid" in call for call in calls)
    assert any("http://127.0.0.1:18080/api/assistant/health" in call for call in calls)
    assert any("http://127.0.0.1:18080/api/assistant/ready" in call for call in calls)
    assert any("http://127.0.0.1:18080/api/assistant/chat" in call for call in calls)
    assert any("http://public-api-closed:8000/health" in call for call in calls)


def test_public_smoke_can_validate_question_collection_notice(
    tmp_path: Path,
) -> None:
    fake_curl_log = tmp_path / "curl.log"
    _write_fake_curl(tmp_path)
    env = _fake_curl_env(tmp_path, fake_curl_log)
    env["PUBLIC_SMOKE_CHECK_QUESTION_COLLECTION"] = "true"

    result = subprocess.run(
        (str(SCRIPTS / "public-smoke.sh"),),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "question collection smoke passed" in result.stdout

    calls = [json.loads(line) for line in fake_curl_log.read_text().splitlines()]
    assert any(
        any("What is Niccolo favorite pizza topping?" in part for part in call)
        for call in calls
    )


def test_public_smoke_fails_when_direct_api_probe_returns_success(
    tmp_path: Path,
) -> None:
    fake_curl_log = tmp_path / "curl.log"
    _write_fake_curl(tmp_path)
    env = _fake_curl_env(tmp_path, fake_curl_log)
    env["PUBLIC_DIRECT_API_PROBE_URL"] = "http://public-api-open:8000/health"

    result = subprocess.run(
        (str(SCRIPTS / "public-smoke.sh"),),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode != 0
    assert (
        "direct API port is publicly reachable: http://public-api-open:8000/health returned 200"
        in result.stderr
    )


def test_nginx_validate_checks_both_public_edge_configs() -> None:
    validate = _script("nginx-validate.sh")

    assert "compose_profile public config >/dev/null" in validate
    assert "compose_profile public-tls config >/dev/null" in validate
    assert "configured_value PUBLIC_HTTP_BIND_ADDRESS" in validate
    assert "configured_value PUBLIC_HTTP_PORT" in validate
    assert "configured_value PUBLIC_HTTPS_BIND_ADDRESS" in validate
    assert "configured_value PUBLIC_HTTPS_PORT" in validate
    assert "deploy/nginx/nginx.conf" in validate
    assert "deploy/nginx/nginx-tls.conf" in validate
    assert "proxy_pass http://api:8000/chat?;" in validate
    assert "proxy_pass http://api:8000/health?;" in validate
    assert "proxy_pass http://api:8000/ready?;" in validate
    assert "listen 443 ssl;" in validate


def test_cleanup_scripts_are_bounded() -> None:
    script_text = "\n".join(
        _read(path)
        for path in sorted(SCRIPTS.glob("*.sh"))
        if path.name != "public-reset-and-setup.sh"
    )
    reset = _script("public-reset-and-setup.sh")

    assert "down --volumes" not in script_text
    assert "down -v" not in script_text
    assert "rm -rf" not in script_text
    assert "remove_compose_volume letsencrypt-certs" not in script_text
    assert "remove_compose_volume letsencrypt-work" not in script_text
    assert "remove_compose_volume acme-challenges" not in script_text
    assert "remove_compose_volume letsencrypt-certs" in reset
    assert "--destroy-certs" in reset
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


def _write_fake_curl(tmp_path: Path) -> None:
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys


args = sys.argv[1:]
with open(os.environ["FAKE_CURL_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")

origin = ""
for index, arg in enumerate(args[:-1]):
    if arg == "-H" and args[index + 1].lower().startswith("origin:"):
        origin = args[index + 1].split(":", 1)[1].strip()

url = ""
for arg in args:
    if arg.startswith(("http://", "https://")):
        url = arg

body = ""
for index, arg in enumerate(args[:-1]):
    if arg == "-d":
        body = args[index + 1]

if url.startswith("http://public-api-open:8000/health"):
    print("200", end="")
elif url.startswith("http://public-api-closed:8000/health"):
    print("000", end="")
elif "-X" in args and "OPTIONS" in args and url.endswith("/api/assistant/chat"):
    if origin in {"https://pigreco.xyz", "https://www.pigreco.xyz"}:
        print("HTTP/1.1 204 No Content")
        print(f"Access-Control-Allow-Origin: {origin}")
        print()
        print("status=204")
    else:
        print("HTTP/1.1 403 Forbidden")
        print()
        print("status=403")
elif url.endswith("/api/assistant/health"):
    print('{"status":"ok"}')
elif url.endswith("/api/assistant/ready"):
    print('{"status":"ready"}')
elif url.endswith("/api/assistant/chat"):
    if "favorite pizza topping" in body:
        print('{"status":"not_answerable","answer":"No verified context.","notices":[{"code":"question_recorded"}]}')
    else:
        print('{"status":"answerable","answer":"OK","notices":[]}')
else:
    print(f"unexpected curl args: {args}", file=sys.stderr)
    sys.exit(2)
""",
        encoding="utf-8",
    )
    fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)


def _fake_curl_env(tmp_path: Path, fake_curl_log: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env["FAKE_CURL_LOG"] = str(fake_curl_log)
    env.pop("PUBLIC_DIRECT_API_PROBE_URL", None)
    env.pop("PUBLIC_SMOKE_BASE_URL", None)
    return env


def _script(name: str) -> str:
    return _read(SCRIPTS / name)


def _all_script_text() -> str:
    return "\n".join(_read(path) for path in sorted(SCRIPTS.glob("*.sh")))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
