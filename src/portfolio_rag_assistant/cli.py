"""Command line entrypoint for local maintenance commands."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from portfolio_rag_assistant.knowledge import (
    KnowledgeIngestionError,
    KnowledgeStore,
    KnowledgeStoreError,
    connect_database,
    load_knowledge_batch,
)


class CommandError(RuntimeError):
    """Raised when command configuration is invalid."""


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CLI process."""

    raise SystemExit(run(argv))


def run(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI and return a process exit code."""

    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    environment = os.environ if env is None else env
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "knowledge" and args.knowledge_command == "ingest":
            return _run_knowledge_ingest(args.files, environment, output)
        parser.print_help(file=errors)
        return 2
    except (CommandError, KnowledgeIngestionError, KnowledgeStoreError) as error:
        print(f"error: {error}", file=errors)
        return 2


def _run_knowledge_ingest(
    files: Sequence[Path],
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    batch = load_knowledge_batch(files)
    database_url = _require_env(env, "DATABASE_URL")
    with connect_database(database_url) as connection:
        KnowledgeStore(connection).ingest_batch(batch)
    print(
        f"ingested {len(batch.sources)} sources and {len(batch.facts)} facts",
        file=stdout,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portfolio-rag-assistant")
    subcommands = parser.add_subparsers(dest="command")

    knowledge = subcommands.add_parser("knowledge")
    knowledge_subcommands = knowledge.add_subparsers(dest="knowledge_command")

    ingest = knowledge_subcommands.add_parser("ingest")
    ingest.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="curated JSON files to ingest",
    )
    return parser


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise CommandError(f"{name} must be set")
    return value.strip()
