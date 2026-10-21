"""Execute the operator scripts without Docker or live certificate changes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("script", "arguments", "renewed", "failure", "reloads"),
    [
        ("public-certbot-status.sh", [], False, False, False),
        ("letsencrypt-renew.sh", ["--dry-run"], False, False, False),
        ("letsencrypt-renew.sh", [], False, False, False),
        ("letsencrypt-renew.sh", [], True, False, True),
        ("letsencrypt-renew.sh", [], False, True, False),
    ],
)
def test_certificate_volume_is_the_renewal_authority(
    tmp_path: Path, script, arguments, renewed, failure, reloads
):
    env_file = tmp_path / "deployment.env"
    env_file.write_text(
        "PUBLIC_SERVER_NAME=board.example.invalid\n"
        "LETSENCRYPT_EMAIL=ops@example.invalid\n"
    )
    calls = tmp_path / "calls.jsonl"
    docker = tmp_path / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['CALLS'], 'a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "if 'renew' in args:\n"
        "    if os.environ['FAILURE'] == '1': sys.exit(17)\n"
        "    if os.environ['RENEWED'] == '1' and '--volume' in args:\n"
        "        mount = args[args.index('--volume') + 1].split(':')[0]\n"
        "        pathlib.Path(mount, 'renewed').touch()\n"
    )
    docker.chmod(0o700)
    env = dict(
        os.environ,
        ENV_FILE=str(env_file),
        PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
        CALLS=str(calls),
        FAILURE=str(int(failure)),
        RENEWED=str(int(renewed)),
    )
    result = subprocess.run(
        [str(ROOT / "scripts/runtime" / script), *arguments],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    assert all("--cert-name" not in command for command in commands)
    assert (result.returncode != 0) == failure
    assert any("reload" in command for command in commands) == reloads
    if reloads:
        assert commands[-2][-2:] == ["nginx", "-t"]
        assert "certificate renewed and nginx reloaded" in result.stdout
    elif not failure and not arguments and script == "letsencrypt-renew.sh":
        assert "no certificates renewed; nginx reload skipped" in result.stdout
