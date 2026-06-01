from __future__ import annotations

import sys
from types import SimpleNamespace

from portfolio_rag_assistant.knowledge import connect_database


def test_connect_database_uses_autocommit_for_long_lived_runtime_connections(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    connection = object()

    def fake_connect(**kwargs: object) -> object:
        calls.append(kwargs)
        return connection

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=fake_connect))

    result = connect_database(
        host="db",
        port=5432,
        name="portfolio",
        user="portfolio_user",
        password="secret",
    )

    assert result is connection
    assert calls == [
        {
            "host": "db",
            "port": 5432,
            "dbname": "portfolio",
            "user": "portfolio_user",
            "password": "secret",
            "autocommit": True,
        }
    ]
