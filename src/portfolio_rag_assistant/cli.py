"""Command line entrypoint for local maintenance commands."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from portfolio_rag_assistant.config import build_llm_provider, load_provider_settings
from portfolio_rag_assistant.knowledge import (
    EmbeddingIndexingError,
    KnowledgeIngestionError,
    KnowledgeStore,
    KnowledgeStoreError,
    KnowledgeValidationError,
    connect_database,
    index_embeddings,
    load_knowledge_batch,
    validate_knowledge_files,
)
from portfolio_rag_assistant.provider import LLMProviderError


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
        if args.command == "knowledge":
            if args.knowledge_command == "validate":
                return _run_knowledge_validate(args.files, output)
            if args.knowledge_command == "ingest":
                return _run_knowledge_ingest(args.files, environment, output)
            if args.knowledge_command == "index-embeddings":
                return _run_knowledge_index_embeddings(environment, output)
        parser.print_help(file=errors)
        return 2
    except (
        CommandError,
        EmbeddingIndexingError,
        KnowledgeIngestionError,
        KnowledgeStoreError,
        KnowledgeValidationError,
        LLMProviderError,
    ) as error:
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


def _run_knowledge_validate(files: Sequence[Path], stdout: TextIO) -> int:
    report = validate_knowledge_files(files)
    print(
        "validated "
        f"{report.source_count} sources, "
        f"{report.fact_count} facts, "
        f"{report.chunk_count} chunks",
        file=stdout,
    )
    return 0


def _run_knowledge_index_embeddings(
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    database_url = _require_env(env, "DATABASE_URL")
    provider_settings = load_provider_settings(env)
    provider = build_llm_provider(provider_settings)
    with connect_database(database_url) as connection:
        result = asyncio.run(
            index_embeddings(
                store=KnowledgeStore(connection),
                provider=provider,
                backend=provider_settings.backend,
                model=provider_settings.embedding_model,
            )
        )
    print(f"indexed {result.indexed_count} chunk embeddings", file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portfolio-rag-assistant")
    subcommands = parser.add_subparsers(dest="command")

    knowledge = subcommands.add_parser("knowledge")
    knowledge_subcommands = knowledge.add_subparsers(dest="knowledge_command")

    validate = knowledge_subcommands.add_parser("validate")
    validate.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="curated JSON files to validate",
    )

    ingest = knowledge_subcommands.add_parser("ingest")
    ingest.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="curated JSON files to ingest",
    )
    knowledge_subcommands.add_parser("index-embeddings")
    return parser


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise CommandError(f"{name} must be set")
    return value.strip()
