"""Command line entry point.

  tailorlock render                      render the untouched master
  tailorlock tailor jobs/x.md            run the propose/validate/render loop (anthropic by default)
  tailorlock tailor jobs/x.md --provider baseline
  tailorlock validate patch.json         validate a patch file
  tailorlock runs                        show the audit log
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import paths
from .diff import diff, format_diff
from .patch import apply_patch
from .render import render
from .schema import Patch, load_policy, load_resume
from .store import Store
from .tailor import make_provider, run_tailor
from .validate import validate_patch


def cmd_render(args) -> int:
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    out = Path(args.out) if args.out else paths.OUT / "master.pdf"
    r = render(master, out, page_limit=policy.page_limit)
    print(f"ok={r.ok} pages={r.pages} {r.seconds:.2f}s -> {r.pdf_path}")
    for e in r.errors:
        print("  ", e)
    return 0 if r.ok else 1


def cmd_validate(args) -> int:
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    patch = Patch.model_validate(json.loads(Path(args.patch).read_text()))
    issues = validate_patch(master, policy, patch)
    for i in issues:
        print(i)
    errs = [i for i in issues if i.severity == "error"]
    print(f"{len(errs)} errors, {len(issues) - len(errs)} warnings")
    if not errs and args.render:
        v = apply_patch(master, patch)
        r = render(v, paths.OUT / "validate.pdf", page_limit=policy.page_limit)
        print(f"render ok={r.ok} pages={r.pages} -> {r.pdf_path}")
        print(format_diff(diff(master, v, patch)))
    return 1 if errs else 0


def cmd_tailor(args) -> int:
    provider = make_provider(args.provider, model=args.model, effort=args.effort, fallbacks=not args.no_fallbacks)
    res = run_tailor(Path(args.job), provider, max_attempts=args.attempts, note=args.note)
    print(res.summary())
    if res.ok and args.diff:
        print()
        print(format_diff(res.diff))
    return 0 if res.ok else 1


def cmd_runs(args) -> int:
    store = Store()
    rows = store.list_runs(limit=args.limit, job=args.job)
    if not rows:
        print("no runs yet")
        return 0
    print(f"{'id':>4} {'status':9} {'pages':5} {'cost$':>8} {'secs':>6} {'provider':12} {'attempt':7} job")
    for r in rows:
        print(f"{r['id']:>4} {r['status']:9} {str(r['pages'] or '-'):5} {r['cost_usd'] or 0:>8.4f} {r['seconds'] or 0:>6.1f} {r['provider']:12} {r['attempt']:7} {r['job']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tailorlock", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render the untouched master")
    r.add_argument("--out")
    r.set_defaults(fn=cmd_render)

    v = sub.add_parser("validate", help="validate a patch json file")
    v.add_argument("patch")
    v.add_argument("--render", action="store_true")
    v.set_defaults(fn=cmd_validate)

    t = sub.add_parser("tailor", help="propose/validate/render loop for a job")
    t.add_argument("job")
    t.add_argument("--provider", choices=["anthropic", "baseline"], default="anthropic")
    t.add_argument("--model", default=None)
    t.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    t.add_argument("--attempts", type=int, default=3)
    t.add_argument("--no-fallbacks", action="store_true", help="disable server-side refusal fallback")
    t.add_argument("--note", default=None)
    t.add_argument("--diff", action="store_true", help="print the field diff when done")
    t.set_defaults(fn=cmd_tailor)

    ru = sub.add_parser("runs", help="show the audit log")
    ru.add_argument("--limit", type=int, default=20)
    ru.add_argument("--job", default=None)
    ru.set_defaults(fn=cmd_runs)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
