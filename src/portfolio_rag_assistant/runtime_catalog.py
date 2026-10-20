"""Read-only declaration of the application's selected Ollama models."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

import httpx


class CatalogExportError(ValueError):
    """The selected provider cannot supply a trustworthy declaration."""


def read_metadata(base: str, path: str, payload: dict | None = None) -> dict:
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        with client.stream(
            "POST" if payload else "GET", base + path, json=payload
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1048576:
                    raise CatalogExportError(
                        "Provider metadata exceeds the export limit"
                    )
    import json

    result = json.loads(body)
    if not isinstance(result, dict):
        raise CatalogExportError("Provider metadata must be an object")
    return result


def export_catalog(
    env: Mapping[str, str],
    *,
    source_commit: str,
    chat_context: int,
    chat_output: int,
    embedding_context: int,
    read: Callable[..., dict[str, Any]] = read_metadata,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise CatalogExportError("Supply the full application source commit")
    if env.get("CHAT_BACKEND") != "ollama" or env.get("EMBEDDING_BACKEND") != "ollama":
        raise CatalogExportError("Both configured selections must use Ollama")
    base = env.get("CHAT_BASE_URL", "").rstrip("/")
    if not base.endswith("/api") or base != env.get("EMBEDDING_BASE_URL", "").rstrip(
        "/"
    ):
        raise CatalogExportError(
            "Selected models must share the configured native Ollama API"
        )
    root = base[:-4]
    if (
        any(
            type(v) is not int or v <= 0
            for v in (chat_context, chat_output, embedding_context)
        )
        or chat_output > chat_context
    ):
        raise CatalogExportError("Invalid configured token limits")
    tags = read(root, "/api/tags")["models"]
    models = []
    for mode, variable, context, output in [
        ("chat", "CHAT_MODEL", chat_context, chat_output),
        ("embedding", "EMBEDDING_MODEL", embedding_context, None),
    ]:
        native = env.get(variable, "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", native):
            raise CatalogExportError("Invalid configured model name")
        canonical = native if ":" in native.rsplit("/", 1)[-1] else native + ":latest"
        matches = [
            m for m in tags if m.get("name") == canonical or m.get("model") == canonical
        ]
        if len(matches) != 1 or not re.fullmatch(
            r"[0-9a-f]{64}", matches[0].get("digest", "")
        ):
            raise CatalogExportError("Selected model is not uniquely installed")
        details = read(root, "/api/show", {"model": native})
        capabilities = details.get("capabilities", [])
        if ("completion" if mode == "chat" else "embedding") not in capabilities:
            raise CatalogExportError(
                "Native capabilities disagree with the configured role"
            )
        info = details["model_info"]
        architecture = info["general.architecture"]
        maximum = info[architecture + ".context_length"]
        if type(maximum) is not int or context > maximum:
            raise CatalogExportError(
                "Configured context exceeds native architectural metadata"
            )
        entry = {
            "id": native.replace(":", "-").replace("/", "-"),
            "native_id": native,
            "digest": matches[0]["digest"],
            "mode": mode,
            "context_window": context,
            "max_context_window": maximum,
            "max_output_tokens": output,
            "supports_tools": mode == "chat" and "tools" in capabilities,
            "supports_reasoning": "thinking" in capabilities,
        }
        if mode == "embedding":
            dimensions = info[architecture + ".embedding_length"]
            if type(dimensions) is not int or dimensions <= 0:
                raise CatalogExportError("Invalid embedding dimensions")
            entry["embedding_dimensions"] = dimensions
        models.append(entry)
    if len({m["id"] for m in models}) != len(models):
        raise CatalogExportError("Configured selections collide")
    return {
        "schema_version": 1,
        "provider": "ollama",
        "source": {"repository": "psychic-waddle", "commit": source_commit},
        "models": models,
    }
