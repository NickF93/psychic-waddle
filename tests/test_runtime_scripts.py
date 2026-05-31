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


def test_cleanup_scripts_are_bounded() -> None:
    script_text = _all_script_text()

    assert "down --volumes" not in script_text
    assert "down -v" not in script_text
    assert "rm -rf" not in script_text
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
