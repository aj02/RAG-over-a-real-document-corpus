"""LLM provider interface.

Both providers expose a single ``complete_json`` call that:
  - sends a system + user prompt
  - asks the model for JSON output
  - returns the raw text plus a token-usage estimate

We keep the interface narrow because regrag has exactly one LLM use case
(synthesise a cited answer from retrieved context). Adding a streaming or
tool-use variant would just bloat the abstraction for no benefit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMClient(Protocol):
    """Provider-agnostic client surface."""

    name: str

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:  # pragma: no cover - protocol
        ...
