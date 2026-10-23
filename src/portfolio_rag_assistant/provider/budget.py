"""Bound input per configured target without dropping approved evidence."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .contract import LLMInputBudgetError, LLMProviderConfigurationError


@lru_cache(maxsize=8)
def _tokenizer(path):
    from tokenizers import Tokenizer

    try:
        tokenizer = Tokenizer.from_file(str(Path(path)))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        return tokenizer
    except Exception as error:
        raise LLMProviderConfigurationError(
            "input tokenizer cannot be loaded"
        ) from error


@dataclass(frozen=True)
class InputBudget:
    max_bytes: int = 65536
    context_tokens: int | None = None
    tokenizer_path: str | None = None
    framing_reserve: int = 256

    def __post_init__(self):
        for value in (self.max_bytes, self.framing_reserve, self.context_tokens):
            if value is not None and (type(value) is not int or value <= 0):
                raise LLMProviderConfigurationError(
                    "input limits must be positive integers"
                )
        if self.tokenizer_path:
            _tokenizer(self.tokenizer_path)

    def check(self, request):
        size = sum(len(m.content.encode("utf-8")) for m in request.messages)
        if size > self.max_bytes:
            raise LLMInputBudgetError("approved input exceeds target byte budget")
        if self.context_tokens is not None:
            if self.tokenizer_path:
                tokenizer = _tokenizer(self.tokenizer_path)
                count = sum(
                    len(tokenizer.encode(m.content, add_special_tokens=False).ids)
                    for m in request.messages
                )
            else:
                # A deliberately conservative admission estimate, not exact usage.
                count = size
            if (
                count + self.framing_reserve + (request.max_tokens or 0)
                > self.context_tokens
            ):
                raise LLMInputBudgetError(
                    "approved input exceeds reserved target context"
                )
