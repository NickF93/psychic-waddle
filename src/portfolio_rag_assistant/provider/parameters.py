"""Validated configuration mapping for generation options, independent of I/O."""

from dataclasses import dataclass
from pathlib import Path
import json

from .contract import ChatRequest, LLMProviderConfigurationError

CONTROLS = frozenset({"temperature", "top_p", "max_tokens", "reasoning_effort"})
ROOTS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "reasoning",
        "reasoning_effort",
        "thinking",
        "think",
        "options",
        "chat_template_kwargs",
    }
)
DEFAULT_PROFILES = Path(__file__).resolve().parents[1] / "generation-profiles.json"


def _put(body, path, value):
    parts = path.split(".")
    current = body
    for part in parts[:-1]:
        current = current.setdefault(part, {})
        if not isinstance(current, dict):
            raise LLMProviderConfigurationError("generation mapping conflicts")
    if parts[-1] in current:
        raise LLMProviderConfigurationError("generation mapping conflicts")
    current[parts[-1]] = value


@dataclass(frozen=True)
class ParameterProfile:
    paths: dict
    reasoning: dict
    efforts: tuple

    @classmethod
    def load(cls, name, path=DEFAULT_PROFILES):
        try:
            raw = json.loads(Path(path).read_text())[name]
            if set(raw) != {"paths", "reasoning", "efforts"}:
                raise ValueError()
            paths, reasoning, efforts = raw["paths"], raw["reasoning"], raw["efforts"]
            if (
                not isinstance(paths, dict)
                or set(paths) - CONTROLS
                or not isinstance(reasoning, dict)
                or set(reasoning) - {"on", "off"}
                or not isinstance(efforts, list)
                or any(not isinstance(e, str) or not e for e in efforts)
            ):
                raise ValueError()
            for mapping in (paths, *reasoning.values()):
                if not isinstance(mapping, dict):
                    raise ValueError()
                for key, value in mapping.items():
                    target = value if mapping is paths else key
                    if (
                        not isinstance(target, str)
                        or target.split(".")[0] not in ROOTS
                        or any(not p.isidentifier() for p in target.split("."))
                    ):
                        raise ValueError()
                    if mapping is not paths and (
                        not isinstance(value, (bool, str, int))
                        or isinstance(value, str)
                        and not value
                    ):
                        raise ValueError()
            if "reasoning_effort" not in paths and efforts:
                raise ValueError()
            profile = cls(dict(paths), dict(reasoning), tuple(efforts))
            # Reject overlapping field paths, including parent/child collisions.
            for mode in ("default", *reasoning):
                fields = [
                    p
                    for k, p in paths.items()
                    if mode != "off" or k != "reasoning_effort"
                ] + [
                    p
                    for p in reasoning.get(mode, {})
                    if not (mode == "on" and p == paths.get("reasoning_effort"))
                ]
                for i, field in enumerate(fields):
                    if any(
                        field == other
                        or field.startswith(other + ".")
                        or other.startswith(field + ".")
                        for other in fields[i + 1 :]
                    ):
                        raise ValueError()
            return profile
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise LLMProviderConfigurationError(
                "invalid generation parameter profile"
            ) from error

    def encode(self, request: ChatRequest):
        result = {}
        if request.reasoning_mode != "default":
            if request.reasoning_mode not in self.reasoning:
                raise LLMProviderConfigurationError(
                    "reasoning mode unsupported by configured target"
                )
            for path, value in self.reasoning[request.reasoning_mode].items():
                if request.reasoning_effort is not None and path == self.paths.get(
                    "reasoning_effort"
                ):
                    continue
                _put(result, path, value)
        if (
            request.reasoning_effort is not None
            and request.reasoning_effort not in self.efforts
        ):
            raise LLMProviderConfigurationError(
                "reasoning effort unsupported by configured target"
            )
        for field in CONTROLS:
            value = getattr(request, field)
            if value is not None:
                if field not in self.paths:
                    raise LLMProviderConfigurationError(
                        f"{field} unsupported by configured target"
                    )
                _put(result, self.paths[field], value)
        return result


def chat_payload(request, *, stream, profile):
    body = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": stream,
    }
    body.update(profile.encode(request))
    return body
