"""The tailoring loop: propose -> validate -> render -> check -> retry with
feedback. The model never decides whether its output is good; the validator
and the renderer do. Every attempt is logged."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .cost import Usage, estimate_usd
from .diff import diff, format_diff
from .patch import apply_patch
from .render import render
from .schema import Patch, Policy, Resume, load_policy, load_resume
from .store import Store
from .validate import errors_only, validate_patch


@dataclass
class Attempt:
    n: int
    status: str  # ok | invalid | overflow | render_error | provider_error
    issues: list[str]
    pages: int = 0
    usage: Usage = field(default_factory=Usage)
    seconds: float = 0.0
    run_id: int | None = None


@dataclass
class RunResult:
    job: str
    ok: bool
    attempts: list[Attempt]
    patch: Patch | None
    variant: Resume | None
    pdf_path: Path | None
    diff: dict
    usage: Usage
    cost_usd: float
    provider: str
    model: str

    def summary(self) -> str:
        lines = [
            f"job={self.job} provider={self.provider} model={self.model} ok={self.ok} attempts={len(self.attempts)}",
            f"tokens in={self.usage.input_tokens} out={self.usage.output_tokens} cache_read={self.usage.cache_read_tokens} cost=${self.cost_usd:.4f}",
        ]
        for a in self.attempts:
            lines.append(f"  attempt {a.n}: {a.status} pages={a.pages} {a.seconds:.1f}s" + (f" issues={len(a.issues)}" if a.issues else ""))
            for i in a.issues[:6]:
                lines.append(f"      - {i}")
        if self.pdf_path:
            lines.append(f"pdf={self.pdf_path}")
        return "\n".join(lines)


def job_slug(job_path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", job_path.stem.lower()).strip("-")


def check_patch(master: Resume, policy: Policy, patch: Patch, out_pdf: Path) -> tuple[str, list[str], int, Resume | None]:
    """Validate then render. Returns (status, issue strings, pages, variant)."""
    issues = validate_patch(master, policy, patch)
    errs = errors_only(issues)
    if errs:
        return "invalid", [str(i) for i in issues], 0, None
    variant = apply_patch(master, patch)
    r = render(variant, out_pdf, page_limit=policy.page_limit)
    if not r.ok:
        status = "overflow" if any(e.startswith("page_overflow") for e in r.errors) else "render_error"
        return status, [str(i) for i in issues] + r.errors, r.pages, variant
    return "ok", [str(i) for i in issues], r.pages, variant


def run_tailor(
    job_path: Path,
    provider,
    max_attempts: int = 3,
    master_path: Path | None = None,
    policy_path: Path | None = None,
    out_dir: Path | None = None,
    store: Store | None = None,
    note: str | None = None,
) -> RunResult:
    master = load_resume(master_path or paths.MASTER)
    policy = load_policy(policy_path or paths.POLICY)
    jd_text = Path(job_path).read_text(encoding="utf-8")
    slug = job_slug(Path(job_path))
    out_dir = out_dir or (paths.OUT / slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = store or Store()

    total = Usage()
    attempts: list[Attempt] = []
    feedback: list[str] = []
    final_patch: Patch | None = None
    final_variant: Resume | None = None
    final_pdf: Path | None = None

    for n in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        try:
            patch, usage = provider.propose(master, policy, jd_text, feedback)
        except Exception as exc:
            a = Attempt(n=n, status="provider_error", issues=[f"{type(exc).__name__}: {exc}"], seconds=time.perf_counter() - t0)
            attempts.append(a)
            a.run_id = store.log_run(job=slug, provider=provider.name, model=provider.model, attempt=n, status=a.status,
                                     n_errors=1, errors_json=a.issues, seconds=a.seconds, note=note)
            break
        total.add(usage)
        pdf = out_dir / f"{slug}.attempt{n}.pdf"
        status, issues, pages, variant = check_patch(master, policy, patch, pdf)
        a = Attempt(n=n, status=status, issues=issues, pages=pages, usage=usage, seconds=time.perf_counter() - t0)
        attempts.append(a)
        d = diff(master, variant, patch) if variant else {}
        cost, _ = estimate_usd(provider.model, usage)
        a.run_id = store.log_run(
            job=slug, provider=provider.name, model=provider.model, attempt=n, status=status, pages=pages,
            n_errors=len([i for i in issues if i.startswith("[error]") or "overflow" in i or "typst" in i]),
            errors_json=issues, patch_json=patch.model_dump(mode="json"), diff_json=d,
            pdf_path=str(pdf) if status == "ok" else None,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_read=usage.cache_read_tokens, cache_write=usage.cache_write_tokens,
            cost_usd=cost, seconds=a.seconds, note=note,
        )
        if status == "ok":
            final_patch, final_variant, final_pdf = patch, variant, pdf
            # also write the artefacts a reviewer wants next to the pdf
            (out_dir / f"{slug}.patch.json").write_text(json.dumps(patch.model_dump(mode="json"), indent=2, ensure_ascii=False))
            (out_dir / f"{slug}.diff.txt").write_text(format_diff(d))
            final_pdf = pdf.rename(out_dir / f"{slug}.pdf")
            break
        feedback = [i for i in issues if not i.startswith("[warning]")]

    cost, _ = estimate_usd(provider.model, total)
    return RunResult(
        job=slug, ok=final_patch is not None, attempts=attempts, patch=final_patch, variant=final_variant,
        pdf_path=final_pdf, diff=diff(master, final_variant, final_patch) if final_variant else {},
        usage=total, cost_usd=cost, provider=provider.name, model=provider.model,
    )


def make_provider(name: str, model: str | None = None, effort: str = "medium", fallbacks: bool = True):
    if name == "baseline":
        from .baseline import BaselineProvider
        return BaselineProvider()
    if name == "anthropic":
        from .llm import DEFAULT_MODEL, AnthropicProvider
        return AnthropicProvider(model=model or DEFAULT_MODEL, effort=effort, fallbacks=fallbacks)
    raise ValueError(f"unknown provider '{name}'")
