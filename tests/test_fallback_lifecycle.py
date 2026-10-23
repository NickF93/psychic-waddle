import os
from pathlib import Path
import subprocess

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/runtime"


def run_phase(tmp_path, phase, extra=""):
    log = tmp_path / "commands"
    docker = tmp_path / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$COMMAND_LOG"\n')
    docker.chmod(0o700)
    env_file = tmp_path / "runtime.env"
    env_file.write_text(
        "CHAT_BACKEND=openai-compatible\nEMBEDDING_BACKEND=openai-compatible\n"
        "CHAT_FALLBACK_BACKEND=ollama\nCHAT_FALLBACK_MODEL=local-model\n"
        "CHAT_FALLBACK_BASE_URL=http://ollama:11434/api\nOLLAMA_KEEP_ALIVE=-1\n" + extra
    )
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "ENV_FILE": str(env_file),
        "COMMAND_LOG": str(log),
    }
    result = subprocess.run(
        [
            "sh",
            "-c",
            'SCRIPT_DIR=$1; . "$SCRIPT_DIR/_common.sh"; chat_fallback_phase "$2"',
            "test",
            str(SCRIPTS),
            phase,
        ],
        env=env,
        text=True,
        capture_output=True,
    )
    return result, log.read_text() if log.exists() else ""


def test_fallback_setup_starts_pulls_and_preloads_the_selected_model(tmp_path):
    result, log = run_phase(tmp_path, "setup")
    assert result.returncode == 0, result.stderr
    assert "up --wait" in log and "ollama pull local-model" in log
    assert (
        "runtime preload-ollama-model --base-url http://ollama:11434/api --model local-model"
        in log
    )
    assert "local chat fallback ready" in result.stdout


def test_fallback_start_reuses_installed_model_without_pulling(tmp_path):
    result, log = run_phase(tmp_path, "start")
    assert (
        result.returncode == 0 and "preload-ollama-model" in log and " pull " not in log
    )


@pytest.mark.parametrize(
    "phase,expected", [("stop", "stop ollama"), ("down", "rm --stop --force ollama")]
)
def test_independent_fallback_lifecycle_targets_only_its_container(
    tmp_path, phase, expected
):
    result, log = run_phase(tmp_path, phase)
    assert result.returncode == 0 and expected in log
    assert "--volumes" not in log
