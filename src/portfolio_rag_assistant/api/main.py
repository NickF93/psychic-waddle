"""ASGI entrypoint for the public API."""

from portfolio_rag_assistant.api.composition import create_runtime_api_app
from portfolio_rag_assistant.observability import configure_logging

configure_logging()
app = create_runtime_api_app()
