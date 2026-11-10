"""Tiny keyword extraction for job descriptions. Used by the baseline provider
and by the eval harness to score coverage. Not clever on purpose: it has to be
deterministic and explainable."""
from __future__ import annotations

import re
from collections import Counter

_STOP = set(
    """a an the and or of to in on for with you your we our is are be as at by from that this it its
    they them their will can not no do does have has had who what when where how which than then
    into about over under more most less least very also just only any all each every both either
    neither such other some one two up out off so if but because while until yet own same too
    s t don't doesn't isn't aren't won't can't like get got make made need needs want wants
    work working works day every build built building team teams role job experience years
    people person someone things thing way ways look looking us me my i he she his her""".split()
)

# multi-word terms we want to keep intact
_PHRASES = [
    "claude code", "cursor", "codex", "mcp servers", "mcp server", "mcp", "subagents", "hooks", "skills",
    "custom commands", "evals", "logging", "rag", "vector databases", "vector database", "pgvector",
    "permissions", "memory", "security", "secrets", "cost", "tokens", "git", "pull requests", "apis", "api",
    "databases", "database", "debugging", "n8n", "supabase", "next.js", "nextjs", "react", "typescript",
    "python", "sql", "postgresql", "postgres", "docker", "aws", "github actions", "ci/cd", "streaming",
    "idempotent", "retries", "dead-letter", "stand-ups", "european", "netherlands", "dutch", "remote",
    "anthropic", "openai", "llm", "agents", "agent", "workflows", "automations", "internal tools",
    "integrations", "servers", "reconciliation", "payments", "migrations", "query tuning", "public repo",
]


def extract_keywords(text: str, top: int = 40) -> list[str]:
    low = text.lower()
    found: Counter[str] = Counter()
    for ph in _PHRASES:
        c = len(re.findall(r"(?<![a-z0-9])" + re.escape(ph) + r"(?![a-z0-9])", low))
        if c:
            found[ph] += c * 3  # phrases we know matter get a boost
    for w in re.findall(r"[a-z][a-z0-9+#./-]{2,}", low):
        w = w.strip("./-")
        if w and w not in _STOP and not w.isdigit():
            found[w] += 1
    return [k for k, _ in found.most_common(top)]


def coverage(text: str, keywords: list[str]) -> tuple[float, list[str], list[str]]:
    """Fraction of keywords that appear in text; returns (ratio, hit, missed)."""
    low = text.lower()
    hit = [k for k in keywords if k in low]
    missed = [k for k in keywords if k not in low]
    return (len(hit) / len(keywords) if keywords else 0.0), hit, missed
