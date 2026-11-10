"""Project paths. Everything is relative to the project root so the MCP server,
CLI, evals and hooks agree on where things live."""
from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("TAILORLOCK_ROOT")
    if env:
        return Path(env).resolve()
    # src/tailorlock/paths.py -> project root is three levels up
    return Path(__file__).resolve().parents[2]


ROOT = project_root()
TEMPLATE = ROOT / "template" / "resume.typ"
# The owner's real master is gitignored. A fresh clone falls back to the fictional
# example so `tailorlock render`, the MCP server and the evals work out of the box.
MASTER = ROOT / "data" / "master.yaml"
if not MASTER.exists():
    MASTER = ROOT / "data" / "master.example.yaml"
POLICY = ROOT / "data" / "policy.yaml"
JOBS = ROOT / "jobs"
OUT = ROOT / "out"
DB = ROOT / ".tailorlock.db"
