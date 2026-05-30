"""ASGI entrypoint for the public API."""

from portfolio_rag_assistant.api.composition import create_runtime_api_app

app = create_runtime_api_app()
