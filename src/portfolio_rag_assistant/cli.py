"""Command line entrypoint for local maintenance commands."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TextIO

from portfolio_rag_assistant.api.readiness import (
    DatabaseReadinessService,
    ReadinessCheckError,
)
from portfolio_rag_assistant.config import (
    DatabaseSettings,
    RuntimeConfigurationError,
    build_chat_provider,
    build_embedding_provider,
    load_chat_provider_settings,
    load_database_settings,
    load_embedding_provider_settings,
    load_intent_catalog_settings,
    load_question_collection_settings,
)
from portfolio_rag_assistant.intent import (
    QuestionIntentProfileError,
    SemanticIntentCalibrationError,
    build_near_duplicate_review_report,
    load_semantic_evaluation_cases,
    load_intent_catalog,
    propose_semantic_thresholds,
    write_tmp_json_report,
)
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
from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatProvider,
    ChatRequest,
    EmbeddingProvider,
    EmbeddingRequest,
    LLMProviderError,
)
from portfolio_rag_assistant.questions import (
    QUESTION_REVIEW_CATEGORIES,
    QUESTION_REVIEW_STATES,
    QuestionEvent,
    QuestionReviewError,
    QuestionReviewStore,
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
        if args.command == "knowledge":
            if args.knowledge_command == "validate":
                return _run_knowledge_validate(args.files, output)
            if args.knowledge_command == "ingest":
                return _run_knowledge_ingest(args.files, environment, output)
            if args.knowledge_command == "index-embeddings":
                return _run_knowledge_index_embeddings(environment, output)
        if args.command == "runtime":
            if args.runtime_command == "smoke":
                return _run_runtime_smoke(environment, output)
        if args.command == "intent":
            if args.intent_command == "calibrate-semantic":
                return _run_intent_calibrate_semantic(args, environment, output)
        if args.command == "questions":
            if args.questions_command == "list":
                return _run_questions_list(args, environment, output)
            if args.questions_command == "show":
                return _run_questions_show(args.event_id, environment, output)
            if args.questions_command == "mark":
                return _run_questions_mark(args, environment, output)
            if args.questions_command == "delete":
                return _run_questions_delete(args.event_id, environment, output)
            if args.questions_command == "export":
                return _run_questions_export(args, environment, output)
            if args.questions_command == "review":
                return _run_questions_review(environment)
        parser.print_help(file=errors)
        return 2
    except (
        CommandError,
        EmbeddingIndexingError,
        KnowledgeIngestionError,
        KnowledgeStoreError,
        KnowledgeValidationError,
        QuestionReviewError,
        ReadinessCheckError,
        RuntimeConfigurationError,
        LLMProviderError,
        QuestionIntentProfileError,
        SemanticIntentCalibrationError,
    ) as error:
        print(f"error: {error}", file=errors)
        return 2


def _run_knowledge_ingest(
    files: Sequence[Path],
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    batch = load_knowledge_batch(files)
    database_settings = load_database_settings(env)
    with _connect_database(database_settings) as connection:
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


def _run_questions_list(
    args: argparse.Namespace,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    with _question_review_store(env) as store:
        events = store.list_events(state=args.state, limit=args.limit)
    _print_question_table(events, stdout)
    return 0


def _run_questions_show(
    event_id: int,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    with _question_review_store(env) as store:
        event = store.get_event(event_id)
    _print_question_detail(event, stdout)
    return 0


def _run_questions_mark(
    args: argparse.Namespace,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    with _question_review_store(env) as store:
        event = store.mark_event(
            args.event_id,
            state=args.state,
            category=args.category,
            note=args.note,
        )
    print(f"marked question event {event.id} as {event.review_state}", file=stdout)
    return 0


def _run_questions_delete(
    event_id: int,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    with _question_review_store(env) as store:
        deleted = store.delete_event(event_id)
    if not deleted:
        raise CommandError("question event not found")
    print(f"deleted question event {event_id}", file=stdout)
    return 0


def _run_questions_export(
    args: argparse.Namespace,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    if args.format != "jsonl":
        raise CommandError("questions export supports only jsonl")
    with _question_review_store(env) as store:
        events = store.export_events(state=args.state)
    for event in events:
        print(json.dumps(_question_event_json(event), ensure_ascii=False), file=stdout)
    return 0


def _run_questions_review(env: Mapping[str, str]) -> int:
    with _question_review_store(env) as store:
        _run_question_review_tui(store)
    return 0


def _run_knowledge_index_embeddings(
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    database_settings = load_database_settings(env)
    provider_settings = load_embedding_provider_settings(env)
    provider = build_embedding_provider(provider_settings)
    with _connect_database(database_settings) as connection:
        result = asyncio.run(
            index_embeddings(
                store=KnowledgeStore(connection),
                provider=provider,
                backend=provider_settings.backend,
                model=provider_settings.model,
            )
        )
    print(f"indexed {result.indexed_count} chunk embeddings", file=stdout)
    return 0


def _run_runtime_smoke(env: Mapping[str, str], stdout: TextIO) -> int:
    database_settings = load_database_settings(env)
    chat_settings = load_chat_provider_settings(env)
    embedding_settings = load_embedding_provider_settings(env)
    question_collection_settings = load_question_collection_settings(env)
    intent_catalog_settings = load_intent_catalog_settings(env)
    intent_catalog = load_intent_catalog(intent_catalog_settings.path)
    _require_matching_semantic_calibration(
        configured_backend=embedding_settings.backend,
        configured_model=embedding_settings.model,
        calibrated_backend=intent_catalog.semantic_calibration.embedding_backend,
        calibrated_model=intent_catalog.semantic_calibration.embedding_model,
    )
    chat_provider = build_chat_provider(chat_settings)
    embedding_provider = build_embedding_provider(embedding_settings)

    with _connect_database(database_settings) as connection:
        asyncio.run(
            DatabaseReadinessService(
                connection=connection,
                embedding_backend=embedding_settings.backend,
                embedding_model=embedding_settings.model,
                question_collection_enabled=question_collection_settings.enabled,
            ).check()
        )

    asyncio.run(
        _check_provider_reachability(
            chat_provider=chat_provider,
            chat_model=chat_settings.model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_settings.model,
        )
    )
    print(
        "runtime smoke passed: database ready, embeddings ready, providers reachable",
        file=stdout,
    )
    return 0


def _run_intent_calibrate_semantic(
    args: argparse.Namespace,
    env: Mapping[str, str],
    stdout: TextIO,
) -> int:
    embedding_settings = load_embedding_provider_settings(env)
    intent_catalog_settings = load_intent_catalog_settings(env)
    intent_catalog = load_intent_catalog(intent_catalog_settings.path)
    _require_matching_semantic_calibration(
        configured_backend=embedding_settings.backend,
        configured_model=embedding_settings.model,
        calibrated_backend=intent_catalog.semantic_calibration.embedding_backend,
        calibrated_model=intent_catalog.semantic_calibration.embedding_model,
    )
    cases = load_semantic_evaluation_cases(
        path=args.evaluation,
        catalog=intent_catalog,
    )
    write_tmp_json_report(
        args.near_duplicate_report,
        build_near_duplicate_review_report(catalog=intent_catalog, cases=cases),
    )
    report = asyncio.run(
        propose_semantic_thresholds(
            catalog=intent_catalog,
            provider=build_embedding_provider(embedding_settings),
            embedding_model=embedding_settings.model,
            evaluation_path=args.evaluation,
        )
    )
    print(json.dumps(report.to_json(), indent=2, sort_keys=True), file=stdout)
    return 0


def _require_matching_semantic_calibration(
    *,
    configured_backend: str,
    configured_model: str,
    calibrated_backend: str,
    calibrated_model: str,
) -> None:
    if (
        configured_backend != calibrated_backend
        or configured_model != calibrated_model
    ):
        raise CommandError(
            "intent semantic calibration must match configured embedding backend "
            "and model"
        )


async def _check_provider_reachability(
    *,
    chat_provider: ChatProvider,
    chat_model: str,
    embedding_provider: EmbeddingProvider,
    embedding_model: str,
) -> None:
    embedding_response = await embedding_provider.embed(
        EmbeddingRequest(model=embedding_model, inputs=("runtime smoke",))
    )
    if len(embedding_response.embeddings) != 1:
        raise CommandError("embedding provider returned the wrong embedding count")
    await chat_provider.chat(
        ChatRequest(
            model=chat_model,
            messages=(ChatMessage(role="user", content="Reply with OK."),),
            temperature=0.0,
            max_tokens=8,
        )
    )


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

    runtime = subcommands.add_parser("runtime")
    runtime_subcommands = runtime.add_subparsers(dest="runtime_command")
    runtime_subcommands.add_parser("smoke")

    intent = subcommands.add_parser("intent")
    intent_subcommands = intent.add_subparsers(dest="intent_command")
    calibrate_semantic = intent_subcommands.add_parser("calibrate-semantic")
    calibrate_semantic.add_argument(
        "--evaluation",
        required=True,
        type=Path,
        help="labeled semantic intent calibration fixture",
    )
    calibrate_semantic.add_argument(
        "--near-duplicate-report",
        required=True,
        type=Path,
        help="manual near-duplicate review report path under /tmp",
    )

    questions = subcommands.add_parser("questions")
    question_subcommands = questions.add_subparsers(dest="questions_command")

    list_questions = question_subcommands.add_parser("list")
    list_questions.add_argument("--state", choices=sorted(QUESTION_REVIEW_STATES))
    list_questions.add_argument("--limit", type=int, default=50)

    show_question = question_subcommands.add_parser("show")
    show_question.add_argument("event_id", type=int)

    mark_question = question_subcommands.add_parser("mark")
    mark_question.add_argument("event_id", type=int)
    mark_question.add_argument("--state", required=True, choices=sorted(QUESTION_REVIEW_STATES))
    mark_question.add_argument("--category", choices=sorted(QUESTION_REVIEW_CATEGORIES))
    mark_question.add_argument("--note")

    delete_question = question_subcommands.add_parser("delete")
    delete_question.add_argument("event_id", type=int)

    export_questions = question_subcommands.add_parser("export")
    export_questions.add_argument("--state", choices=sorted(QUESTION_REVIEW_STATES))
    export_questions.add_argument("--format", choices=("jsonl",), default="jsonl")

    question_subcommands.add_parser("review")
    return parser


def _connect_database(settings: DatabaseSettings) -> object:
    return connect_database(
        host=settings.host,
        port=settings.port,
        name=settings.name,
        user=settings.user,
        password=settings.password,
    )


class _QuestionReviewStoreContext:
    def __init__(self, env: Mapping[str, str]) -> None:
        self._env = env
        self._connection_context: AbstractContextManager[object] | None = None

    def __enter__(self) -> QuestionReviewStore:
        database_settings = load_database_settings(self._env)
        self._connection_context = _connect_database(database_settings)
        connection = self._connection_context.__enter__()
        return QuestionReviewStore(connection)

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._connection_context is not None:
            self._connection_context.__exit__(exc_type, exc, traceback)


def _question_review_store(env: Mapping[str, str]) -> _QuestionReviewStoreContext:
    return _QuestionReviewStoreContext(env)


def _run_question_review_tui(store: QuestionReviewStore) -> None:
    from portfolio_rag_assistant.questions.tui import run_question_review_tui

    run_question_review_tui(store)


def _print_question_table(events: tuple[QuestionEvent, ...], stdout: TextIO) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(title="Collected Questions")
    table.add_column("ID", justify="right")
    table.add_column("State")
    table.add_column("Category")
    table.add_column("Created")
    table.add_column("Question")
    for event in events:
        table.add_row(
            str(event.id),
            event.review_state,
            event.review_category or "",
            event.created_at,
            event.raw_question_text,
        )
    Console(file=stdout, force_terminal=False, color_system=None).print(table)


def _print_question_detail(event: QuestionEvent, stdout: TextIO) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table.grid(padding=(0, 2))
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for field_name, value in _question_event_json(event).items():
        table.add_row(field_name, "" if value is None else str(value))
    Console(file=stdout, force_terminal=False, color_system=None).print(table)


def _question_event_json(event: QuestionEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "raw_question_text": event.raw_question_text,
        "review_state": event.review_state,
        "review_category": event.review_category,
        "review_note": event.review_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
