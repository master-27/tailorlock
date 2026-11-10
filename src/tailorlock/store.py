"""SQLite log of every tailoring run: what was proposed, whether it passed,
how many pages, what it cost. One table, no ORM. This is the audit trail."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from . import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ts            REAL NOT NULL,
  job           TEXT NOT NULL,
  provider      TEXT NOT NULL,
  model         TEXT NOT NULL,
  attempt       INTEGER NOT NULL DEFAULT 1,
  status        TEXT NOT NULL,              -- ok | invalid | overflow | render_error
  pages         INTEGER,
  n_errors      INTEGER NOT NULL DEFAULT 0,
  errors_json   TEXT,
  patch_json    TEXT,
  diff_json     TEXT,
  pdf_path      TEXT,
  input_tokens  INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  cache_read    INTEGER DEFAULT 0,
  cache_write   INTEGER DEFAULT 0,
  cost_usd      REAL DEFAULT 0,
  seconds       REAL DEFAULT 0,
  note          TEXT
);
"""


class Store:
    def __init__(self, db_path: Path | None = None):
        self.path = db_path or paths.DB
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    def log_run(self, **row) -> int:
        row.setdefault("ts", time.time())
        for k in ("errors_json", "patch_json", "diff_json"):
            if k in row and not isinstance(row[k], (str, type(None))):
                row[k] = json.dumps(row[k], ensure_ascii=False)
        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        cur = self.conn.execute(f"INSERT INTO runs ({cols}) VALUES ({qs})", list(row.values()))
        self.conn.commit()
        return int(cur.lastrowid)

    def list_runs(self, limit: int = 20, job: str | None = None) -> list[dict]:
        q = "SELECT id, ts, job, provider, model, attempt, status, pages, n_errors, cost_usd, seconds, pdf_path, note FROM runs"
        args: list = []
        if job:
            q += " WHERE job = ?"
            args.append(job)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def get_run(self, run_id: int) -> dict | None:
        r = self.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(r) if r else None

    def close(self) -> None:
        self.conn.close()
