"""RUN_TLS_INTEGRATION=1: real provider TLS against disposable local endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from portfolio_rag_assistant.provider import (
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    LLMProviderTransportError,
)
from portfolio_rag_assistant.provider.ollama import OllamaProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TLS_INTEGRATION") != "1",
    reason="opt-in socket-based TLS fixture",
)


@pytest.fixture
def tls_endpoint(tmp_path, monkeypatch):
    assert shutil.which("openssl"), "TLS integration requires openssl"
    certificate = tmp_path / "certificate.pem"
    key = tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            )
            if self.path == "/api/embed":
                payload = {"model": "fixture", "embeddings": [[1.0, 0.0]]}
            else:
                payload = {
                    "model": "fixture",
                    "message": {"role": "assistant", "content": "verified"},
                    "done": True,
                    "done_reason": "stop",
                }
            body = json.dumps(payload).encode()
            if request.get("stream"):
                body += b"\n"
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/x-ndjson" if request.get("stream") else "application/json",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    # Use the library's documented trust override, retaining its real transport.
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    worker.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_provider_accepts_valid_tls_for_chat_and_embedding(tls_endpoint):
    provider = OllamaProvider(
        base_url=f"https://localhost:{tls_endpoint}/api", timeout=2
    )
    chat = asyncio.run(
        provider.chat(
            ChatRequest(
                model="fixture",
                messages=(ChatMessage(role="user", content="test"),),
            )
        )
    )
    embedding = asyncio.run(
        provider.embed(
            EmbeddingRequest(
                model="fixture",
                inputs=("test",),
            )
        )
    )

    assert chat.message.content == "verified"
    assert embedding.embeddings == ((1.0, 0.0),)
    assert asyncio.run(_stream(provider)) == ["verified"]


async def _stream(provider):
    return [
        part
        async for part in provider.stream_chat(
            ChatRequest(
                model="fixture",
                messages=(ChatMessage(role="user", content="test"),),
            )
        )
    ]


@pytest.mark.parametrize("failure", ["hostname", "untrusted-chain"])
@pytest.mark.parametrize("operation", ["embed", "chat", "stream"])
def test_provider_rejects_invalid_tls_without_exposing_credentials(
    tls_endpoint,
    monkeypatch,
    failure,
    operation,
):
    host = "127.0.0.1" if failure == "hostname" else "localhost"
    if failure == "untrusted-chain":
        monkeypatch.delenv("SSL_CERT_FILE")
    provider = OllamaProvider(
        base_url=f"https://{host}:{tls_endpoint}/api",
        api_key="fixture-private-key",
        timeout=2,
    )

    with pytest.raises(LLMProviderTransportError) as error:
        if operation == "embed":
            asyncio.run(
                provider.embed(EmbeddingRequest(model="fixture", inputs=("test",)))
            )
        elif operation == "chat":
            asyncio.run(
                provider.chat(
                    ChatRequest(
                        model="fixture",
                        messages=(ChatMessage(role="user", content="test"),),
                    )
                )
            )
        else:
            asyncio.run(_stream(provider))

    assert str(error.value) == (
        "provider stream transport failed"
        if operation == "stream"
        else "provider transport failed"
    )
    assert "fixture-private-key" not in str(error.value)
    assert "https://" not in str(error.value)
