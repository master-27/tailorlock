"""MCP server: the only door through which an agent touches the resume.

Tools are deliberately coarse. The agent cannot write files, cannot see the
template, and cannot skip validation: `render_patch` always validates first,
always checks the page limit, always logs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from . import paths
from .baseline import baseline_patch
from .diff import diff, format_diff
from .keywords import coverage, extract_keywords
from .schema import Patch, load_policy, load_resume
from .store import Store
from .tailor import check_patch, job_slug

server = MCPServer(
    "tailorlock",
    instructions=(
        "Resume tailoring behind a locked template. Flow: get_job -> get_master -> get_policy -> "
        "(optional) baseline_patch -> render_patch (repeat on errors, max 3) -> report diff_text and pdf_path. "
        "You can only propose patches; layout and rules are not yours to change."
    ),
)


def _resolve_job(job: str) -> Path:
    """Accept a slug (nordavo-agentic-ai-engineer), a file name, or a path relative to the project root."""
    cands = [paths.JOBS / f"{job}.md", paths.JOBS / job, paths.ROOT / job]
    for c in cands:
        if c.is_file() and c.resolve().is_relative_to(paths.ROOT):
            return c
    raise FileNotFoundError(f"job '{job}' not found; put it in jobs/<slug>.md or pass a project-relative path")


@server.tool()
def get_job(job: str) -> str:
    """Read a job description. `job` is a slug under jobs/ (e.g. 'nordavo-agentic-ai-engineer') or a project-relative path."""
    return _resolve_job(job).read_text(encoding="utf-8")


@server.tool()
def list_jobs() -> list[str]:
    """List available job description slugs under jobs/."""
    return sorted(p.stem for p in paths.JOBS.glob("*.md"))


@server.tool()
def get_master() -> dict[str, Any]:
    """The master resume as JSON. Every bullet and skill has a stable id; patches reference these ids."""
    return load_resume(paths.MASTER).model_dump(mode="json")


@server.tool()
def get_policy() -> dict[str, Any]:
    """The policy (what may change, within what limits) plus the JSON schema a patch must satisfy."""
    return {"policy": load_policy(paths.POLICY).model_dump(mode="json"), "patch_schema": Patch.model_json_schema()}


@server.tool()
def baseline_patch_for(job: str) -> dict[str, Any]:
    """A deterministic keyword-ranked starting patch for this job. Improve on it; do not return it unchanged."""
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    jd = _resolve_job(job).read_text(encoding="utf-8")
    return baseline_patch(master, policy, jd).model_dump(mode="json")


@server.tool()
def validate_only(patch: dict[str, Any]) -> dict[str, Any]:
    """Validate a patch against master + policy without rendering. Cheap; use it while drafting."""
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    try:
        p = Patch.model_validate(patch)
    except ValidationError as exc:
        return {"ok": False, "errors": [f"schema: {e['loc']} {e['msg']}" for e in exc.errors()]}
    from .validate import validate_patch
    issues = validate_patch(master, policy, p)
    return {"ok": not any(i.severity == "error" for i in issues), "issues": [str(i) for i in issues]}


@server.tool()
def render_patch(patch: dict[str, Any], job: str, note: str = "", attempt: int = 1) -> dict[str, Any]:
    """Validate, apply, render to PDF, check the page limit, log the run.

    Returns ok, pages, errors (fix exactly these and call again), diff_text, pdf_path, keyword coverage, run_id.
    """
    master = load_resume(paths.MASTER)
    policy = load_policy(paths.POLICY)
    job_path = _resolve_job(job)
    slug = job_slug(job_path)
    try:
        p = Patch.model_validate(patch)
    except ValidationError as exc:
        return {"ok": False, "errors": [f"schema: {'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]}

    out_dir = paths.OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / f"{slug}.agent.attempt{attempt}.pdf"
    status, issues, pages, variant = check_patch(master, policy, p, pdf)
    d = diff(master, variant, p) if variant else {}
    jd = job_path.read_text(encoding="utf-8")
    kws = extract_keywords(jd, top=30)
    cov, hit, missed = coverage(variant.plain_text(), kws) if variant else (0.0, [], kws)

    store = Store()
    run_id = store.log_run(
        job=slug, provider="claude-code", model="claude-code", attempt=attempt, status=status, pages=pages,
        n_errors=len([i for i in issues if not i.startswith("[warning]")]) if status != "ok" else 0,
        errors_json=issues, patch_json=p.model_dump(mode="json"), diff_json=d,
        pdf_path=str(pdf) if status == "ok" else None, note=note or None,
    )
    store.close()

    result: dict[str, Any] = {
        "ok": status == "ok",
        "status": status,
        "run_id": run_id,
        "pages": pages,
        "page_limit": policy.page_limit,
        "errors": [i for i in issues if not i.startswith("[warning]")] if status != "ok" else [],
        "warnings": [i for i in issues if i.startswith("[warning]")],
        "keyword_coverage": round(cov, 2),
        "keywords_missed": missed[:12],
    }
    if status == "ok":
        final = out_dir / f"{slug}.agent.pdf"
        pdf.replace(final)
        (out_dir / f"{slug}.agent.patch.json").write_text(json.dumps(p.model_dump(mode="json"), indent=2, ensure_ascii=False))
        result["pdf_path"] = str(final)
        result["diff_text"] = format_diff(d)
    return result


@server.tool()
def list_runs(limit: int = 10, job: str | None = None) -> list[dict[str, Any]]:
    """Recent tailoring runs from the audit log (status, pages, cost, pdf)."""
    store = Store()
    try:
        return store.list_runs(limit=limit, job=job)
    finally:
        store.close()


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
