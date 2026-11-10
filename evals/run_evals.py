"""Eval harness: run the tailoring loop over every JD in evals/jds and score it.

Metrics per JD:
  valid_first_try   did the first patch pass the validator?
  attempts          how many rounds until ok (or failure)
  pages             rendered pages (must be <= policy.page_limit)
  coverage          share of the JD's top-30 keywords present in the variant
  cost_usd, tokens  what it cost
Baseline provider is free and deterministic; it is the floor the LLM has to beat.

  uv run python evals/run_evals.py --provider baseline
  uv run python evals/run_evals.py --provider anthropic --model claude-opus-5-5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tailorlock import paths  # noqa: E402
from tailorlock.keywords import coverage, extract_keywords  # noqa: E402
from tailorlock.schema import load_policy, load_resume  # noqa: E402
from tailorlock.store import Store  # noqa: E402
from tailorlock.tailor import make_provider, run_tailor  # noqa: E402

EXPECT = json.loads((ROOT / "evals" / "expectations.json").read_text()) if (ROOT / "evals" / "expectations.json").exists() else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="baseline", choices=["baseline", "anthropic"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--only", default=None, help="run a single JD slug")
    args = ap.parse_args()

    provider = make_provider(args.provider, model=args.model, effort=args.effort)
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    out_dir = ROOT / "evals" / "results" / f"{provider.name}-{provider.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    store = Store(out_dir / "runs.db")

    rows = []
    for jd in sorted((ROOT / "evals" / "jds").glob("*.md")):
        if args.only and jd.stem != args.only:
            continue
        t0 = time.perf_counter()
        res = run_tailor(jd, provider, max_attempts=args.attempts, out_dir=out_dir / jd.stem, store=store, note="eval")
        kws = extract_keywords(jd.read_text(), top=30)
        cov_master, _, _ = coverage(master.plain_text(), kws)
        cov, hit, missed = coverage(res.variant.plain_text(), kws) if res.variant else (0.0, [], kws)
        row = {
            "jd": jd.stem,
            "ok": res.ok,
            "valid_first_try": bool(res.attempts) and res.attempts[0].status == "ok",
            "attempts": len(res.attempts),
            "pages": res.attempts[-1].pages if res.attempts else 0,
            "coverage": round(cov, 2),
            "coverage_master_all_bullets": round(cov_master, 2),
            "missed": missed[:8],
            "tokens_in": res.usage.input_tokens,
            "tokens_out": res.usage.output_tokens,
            "cache_read": res.usage.cache_read_tokens,
            "cost_usd": round(res.cost_usd, 4),
            "seconds": round(time.perf_counter() - t0, 1),
            "statuses": [a.status for a in res.attempts],
        }
        exp = EXPECT.get(jd.stem, {})
        row["meets_min_coverage"] = cov >= exp.get("min_coverage", 0.0)
        rows.append(row)
        print(f"{jd.stem:34} ok={res.ok!s:5} first_try={row['valid_first_try']!s:5} attempts={row['attempts']} pages={row['pages']} cov={cov:.2f} (master {cov_master:.2f}) cost=${res.cost_usd:.4f} {row['seconds']}s")

    (out_dir / "summary.json").write_text(json.dumps(rows, indent=2))
    md = ["| JD | ok | first try | attempts | pages | coverage | master cov. | cost $ | s |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['jd']} | {r['ok']} | {r['valid_first_try']} | {r['attempts']} | {r['pages']} | {r['coverage']:.2f} | {r['coverage_master_all_bullets']:.2f} | {r['cost_usd']:.4f} | {r['seconds']} |")
    (out_dir / "summary.md").write_text(f"# {provider.name} / {provider.model}\n\n" + "\n".join(md) + "\n")
    n = len(rows) or 1
    print("-" * 100)
    print(f"provider={provider.name} model={provider.model}  pass={sum(r['ok'] for r in rows)}/{len(rows)}  "
          f"first_try={sum(r['valid_first_try'] for r in rows)}/{len(rows)}  "
          f"avg_cov={sum(r['coverage'] for r in rows)/n:.2f}  total_cost=${sum(r['cost_usd'] for r in rows):.4f}  "
          f"meets_min_coverage={sum(r['meets_min_coverage'] for r in rows)}/{len(rows)}")
    print(f"details: {out_dir/'summary.json'}")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
