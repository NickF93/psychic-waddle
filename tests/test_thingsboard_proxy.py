"""Native edge integration: RUN_PROXY_INTEGRATION=1 python -m unittest discover
-s tests -p test_thingsboard_proxy.py -v. Requires Docker and openssl. All objects
are UUID-owned and removed, including after failed setup. No production data.
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NGINX_IMAGE = "nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10"
BACKEND = """from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, time
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *args): pass
    def do_GET(self): self.respond()
    def do_POST(self): self.respond()
    def respond(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "upgrade")
            self.end_headers()
            return
        if self.path.split("?", 1)[0] == "/chat":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"data: first\\n\\n"); self.wfile.flush()
            time.sleep(1)
            self.wfile.write(b"data: second\\n\\n"); self.wfile.flush()
            self.close_connection = True
            return
        data = json.dumps({"service": os.environ["FIXTURE_NAME"], "path": self.path,
                           "headers": dict(self.headers), "size": len(body)}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
"""


def docker(*args: str) -> str:
    return subprocess.check_output(
        ("docker", *args), text=True, stderr=subprocess.STDOUT
    ).strip()


@unittest.skipUnless(
    os.getenv("RUN_PROXY_INTEGRATION") == "1", "opt-in native Docker proxy fixture"
)
class ThingsBoardProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefix = "m17-fixture-" + uuid.uuid4().hex[:12]
        cls.containers = []
        cls.addClassCleanup(cls.cleanup)
        cls.temp = tempfile.TemporaryDirectory(prefix=cls.prefix)
        cls.directory = Path(cls.temp.name)
        docker("network", "create", cls.prefix)
        (cls.directory / "backend.py").write_text(BACKEND)
        image = os.getenv("PROXY_TEST_PYTHON_IMAGE", "python:3.12-alpine")
        for alias, service in [("api", "rag"), ("board", "thingsboard")]:
            name = cls.prefix + "-" + alias
            cls.containers.append(name)
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--network",
                cls.prefix,
                "--network-alias",
                alias,
                "-e",
                "FIXTURE_NAME=" + service,
                "-v",
                str(cls.directory / "backend.py") + ":/fixture.py:ro",
                "--entrypoint",
                "python",
                image,
                "/fixture.py",
            )
        certs = cls.directory / "certs" / "live" / "portfolio-rag-assistant"
        certs.mkdir(parents=True)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(certs / "privkey.pem"),
                "-out",
                str(certs / "fullchain.pem"),
                "-days",
                "1",
                "-subj",
                "/CN=board.test",
            ],
            check=True,
            capture_output=True,
        )
        public = cls.directory / "public"
        public.mkdir()
        config = (ROOT / "deploy/nginx/thingsboard.conf.template").read_text()
        for key, value in {
            "THINGSBOARD_SERVER_NAME": "board.test",
            "THINGSBOARD_UPSTREAM": "board:8000",
            "THINGSBOARD_CERTIFICATE_NAME": "portfolio-rag-assistant",
        }.items():
            config = config.replace("${" + key + "}", value)
        (public / "thingsboard.conf").write_text(config)
        cls.edge = cls.prefix + "-edge"
        cls.containers.append(cls.edge)
        challenges = cls.directory / "challenges"
        challenges.mkdir()
        (challenges / ".well-known/acme-challenge").mkdir(parents=True)
        (challenges / ".well-known/acme-challenge/probe").write_text("fixture")
        docker(
            "run",
            "-d",
            "--name",
            cls.edge,
            "--network",
            cls.prefix,
            "-p",
            "127.0.0.1::443",
            "-p",
            "127.0.0.1::80",
            "-v",
            str(ROOT / "deploy/nginx/nginx-tls.conf") + ":/etc/nginx/nginx.conf:ro",
            "-v",
            str(ROOT / "deploy/nginx/snippets") + ":/etc/nginx/snippets:ro",
            "-v",
            str(public) + ":/etc/nginx/public-services:ro",
            "-v",
            str(cls.directory / "certs") + ":/etc/letsencrypt:ro",
            "-v",
            str(challenges) + ":/var/www/certbot:ro",
            NGINX_IMAGE,
        )
        ports = json.loads(docker("inspect", cls.edge))[0]["NetworkSettings"]["Ports"]
        cls.port = int(ports["443/tcp"][0]["HostPort"])
        cls.http_port = int(ports["80/tcp"][0]["HostPort"])
        for attempt in range(50):
            try:
                status, _, _ = cls.request("/api/assistant/health")
                if status == 200:
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError(
                "Fixture did not become ready: " + docker("logs", cls.edge)
            )

    @classmethod
    def cleanup(cls):
        for name in reversed(cls.containers):
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, check=False
            )
        subprocess.run(
            ["docker", "network", "rm", cls.prefix], capture_output=True, check=False
        )
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    @classmethod
    def request(cls, path, method="GET", body=None, headers=None, host="board.test"):
        # Self-signed certificates are confined to this disposable fixture.
        connection = http.client.HTTPSConnection(
            "127.0.0.1", cls.port, context=ssl._create_unverified_context(), timeout=5
        )
        connection.request(method, path, body, {"Host": host, **(headers or {})})
        response = connection.getresponse()
        status, result_headers = response.status, dict(response.getheaders())
        result = b"" if status == 101 else response.read()
        connection.close()
        return status, result_headers, result

    def test_shared_routes_permissions_and_default_site(self):
        for route in ["health", "ready"]:
            status, _, body = self.request("/api/assistant/" + route)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["service"], "rag")
        self.assertEqual(self.request("/api/assistant/chat")[0], 405)
        self.assertEqual(
            self.request(
                "/api/assistant/health", headers={"Origin": "https://untrusted.test"}
            )[0],
            403,
        )
        self.assertEqual(self.request("/", host="other.test")[0], 404)
        status, _, body = self.request("/dashboards")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["service"], "thingsboard")

    def test_forwarded_headers_and_independent_limits(self):
        status, _, body = self.request(
            "/api/test",
            "POST",
            b"x" * 8192,
            {
                "Forwarded": "spoof",
                "X-Forwarded-For": "spoof",
                "X-Real-IP": "spoof",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Host": "spoof",
                "X-Forwarded-Port": "1",
            },
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        headers = {key.lower(): value for key, value in data["headers"].items()}
        self.assertEqual(data["size"], 8192)
        self.assertEqual(headers["x-forwarded-proto"], "https")
        self.assertEqual(headers["x-forwarded-host"], "board.test")
        self.assertEqual(headers["x-forwarded-port"], "443")
        for header in ["forwarded", "x-forwarded-for", "x-real-ip"]:
            self.assertNotIn(header, headers)
        self.assertEqual(
            self.request("/api/assistant/chat", "POST", b"x" * 8192)[0], 413
        )

    def test_websocket_upgrade(self):
        status, headers, _ = self.request(
            "/api/ws/plugins/telemetry",
            headers={"Connection": "Upgrade", "Upgrade": "websocket"},
        )
        self.assertEqual(status, 101)
        self.assertEqual(headers["Upgrade"].lower(), "websocket")

    def test_device_path_and_query_never_enter_access_log(self):
        secret = "fixture-secret-" + uuid.uuid4().hex
        self.assertEqual(
            self.request(
                "/api/v1/" + secret + "/telemetry?token=" + secret,
                "POST",
                b"{}",
                {"Authorization": "Bearer " + secret},
            )[0],
            200,
        )
        logs = docker("logs", self.edge)
        self.assertNotIn(secret, logs)
        self.assertIn("route=device-api status=200", logs)

    def test_redirect_and_fallback_hosts_never_log_tokens(self):
        secret = "fixture-secret-" + uuid.uuid4().hex
        path = "/api/v1/" + secret + "/telemetry?token=" + secret
        connection = http.client.HTTPConnection("127.0.0.1", self.http_port, timeout=5)
        connection.request("POST", path, b"{}", {"Host": "board.test"})
        response = connection.getresponse()
        self.assertEqual(response.status, 308)
        response.read()
        connection.close()
        self.assertEqual(self.request(path, host="other.test")[0], 404)
        self.assertNotIn(secret, docker("logs", self.edge))

    def test_http_redirect_and_acme(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.http_port, timeout=5)
        connection.request("GET", "/login?return=home", headers={"Host": "board.test"})
        response = connection.getresponse()
        response.read()
        self.assertEqual(response.status, 308)
        self.assertEqual(
            response.getheader("Location"), "https://board.test/login?return=home"
        )
        connection.request(
            "GET", "/.well-known/acme-challenge/probe", headers={"Host": "board.test"}
        )
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read(), b"fixture")
        connection.close()

    def test_rag_stream_is_not_buffered(self):
        connection = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=ssl._create_unverified_context(), timeout=5
        )
        connection.request("POST", "/api/assistant/chat", b"{}", {"Host": "board.test"})
        response = connection.getresponse()
        start = time.monotonic()
        self.assertEqual(response.readline(), b"data: first\n")
        first = time.monotonic() - start
        self.assertIn(b"data: second", response.read())
        self.assertGreater(time.monotonic() - start - first, 0.7)
        connection.close()
