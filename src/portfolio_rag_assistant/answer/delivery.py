"""Explicit generation targets and provisional answer filtering."""

from dataclasses import dataclass
import math

from portfolio_rag_assistant.provider import ChatProvider
from portfolio_rag_assistant.provider.contract import (
    LLMProviderRequestError,
    LLMProviderTransportError,
    LLMProviderResponseError,
)
from portfolio_rag_assistant.answer.contract import AnswerGenerationConfigurationError

SENTINEL = "INSUFFICIENT_APPROVED_CONTEXT"


def failure_reason(error: Exception) -> str:
    """Readable operational reason without upstream message/body disclosure."""
    if isinstance(error, TimeoutError):
        return "deadline reached"
    if isinstance(error, LLMProviderTransportError):
        return "connection or stream transport failed"
    if isinstance(error, LLMProviderRequestError):
        status = error.status_code
        return (
            f"HTTP {status}"
            if isinstance(status, int) and 100 <= status <= 599
            else "request rejected"
        )
    if isinstance(error, LLMProviderResponseError):
        return "invalid or incomplete response"
    return "provider failed"


@dataclass(frozen=True)
class GenerationTarget:
    provider: ChatProvider
    model: str
    timeout: float
    role: str

    def __post_init__(self):
        if not isinstance(self.provider, ChatProvider) or not self.model.strip():
            raise AnswerGenerationConfigurationError("invalid generation target")
        if (
            isinstance(self.timeout, bool)
            or not math.isfinite(self.timeout)
            or self.timeout <= 0
        ):
            raise AnswerGenerationConfigurationError(
                "generation timeout must be finite and positive"
            )


class ProvisionalText:
    """Never emit sentinel fragments, including when split across chunks."""

    def __init__(self):
        self.pending = ""
        self.suppressed = False
        self.text = ""

    def add(self, chunk: str, *, final: bool = False) -> str:
        self.text += chunk
        if self.suppressed:
            return ""
        self.pending += chunk
        if SENTINEL.casefold() in self.pending.casefold():
            self.pending = ""
            self.suppressed = True
            return ""
        # Keep the longest suffix which may become an internal sentinel.
        held = 0
        folded = self.pending.casefold()
        if not final:
            for size in range(1, min(len(SENTINEL), len(folded)) + 1):
                if SENTINEL.casefold().startswith(folded[-size:]):
                    held = size
        result = self.pending[:-held] if held else self.pending
        self.pending = self.pending[-held:] if held else ""
        return result
