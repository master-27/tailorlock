"""Token accounting. Prices are USD per million tokens (Anthropic first-party
rates, cached 2026-10). Unknown models cost 0 and are flagged."""
from __future__ import annotations

from dataclasses import dataclass

PRICES: dict[str, dict[str, float]] = {
    # model: input, output, cache_read, cache_write (per 1M tokens)
    "claude-opus-5-5":   {"in": 4.00, "out": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-5-5":  {"in": 0.10, "out": 0.50,  "cache_read": 0.01, "cache_write": 0.125},
    "baseline":          {"in": 0.0,  "out": 0.0,   "cache_read": 0.0,  "cache_write": 0.0},
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.calls += other.calls


def estimate_usd(model: str, u: Usage) -> tuple[float, bool]:
    """Returns (usd, known_price)."""
    p = PRICES.get(model)
    if p is None:
        return 0.0, False
    usd = (
        u.input_tokens * p["in"]
        + u.output_tokens * p["out"]
        + u.cache_read_tokens * p["cache_read"]
        + u.cache_write_tokens * p["cache_write"]
    ) / 1_000_000
    return round(usd, 6), True
