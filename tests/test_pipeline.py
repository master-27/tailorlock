import json
from pathlib import Path

from tailorlock.baseline import BaselineProvider, baseline_patch
from tailorlock.diff import diff, format_diff
from tailorlock.patch import apply_patch
from tailorlock.render import render, to_markup
from tailorlock.store import Store
from tailorlock.tailor import run_tailor
from tailorlock.validate import errors_only, validate_patch

ROOT = Path(__file__).resolve().parents[1]
JD = ROOT / "jobs" / "nordavo-agentic-ai-engineer.md"
EXAMPLE = ROOT / "data" / "master.example.yaml"  # tests never touch the owner's private master


def test_apply_patch_only_touches_whitelisted_fields(master, good_patch):
    good_patch.sections["exp-acme-sde"].relabel = {"exp-acme-sde-notif": "Event-Driven Processing"}
    v = apply_patch(master, good_patch)
    assert v.basics == master.basics
    assert v.education == master.education
    assert [e.company for e in v.experience] == [e.company for e in master.experience]
    assert [e.start for e in v.experience] == [e.start for e in master.experience]
    assert len(v.experience[0].bullets) == 6
    assert [b.label for b in v.experience[0].bullets if b.id == "exp-acme-sde-notif"] == ["Event-Driven Processing"]
    assert [p.id for p in v.projects] == ["prj-mentor"]


def test_to_markup_escapes_everything_but_bold():
    assert to_markup("**200 Cr+** at #home with $x and _y_ // z") == "*200 Cr+* at \\#home with \\$x and \\_y\\_ \\/\\/ z"
    assert to_markup("#import \"x.typ\"") == "\\#import \"x.typ\""


def test_render_fits_one_page(master, policy, good_patch, tmp_path):
    v = apply_patch(master, good_patch)
    r = render(v, tmp_path / "v.pdf", page_limit=policy.page_limit)
    assert r.ok and r.pages == 1 and r.pdf_path.exists(), r.errors


def test_render_detects_overflow(master, tmp_path):
    m = master.model_copy(deep=True)
    m.summary = " ".join(["Long filler sentence about systems and agents."] * 140)
    r = render(m, tmp_path / "o.pdf", page_limit=1)
    assert not r.ok and r.pages >= 2 and any("page_overflow" in e for e in r.errors)


def test_injection_in_bullet_does_not_execute(master, policy, good_patch, tmp_path):
    good_patch.sections["exp-acme-sde"].rewrites = {
        "exp-acme-sde-infra": 'Containerized services #eval("sys.inputs") #import "x.typ" <lbl> @ref and deployed via ECR, ECS and Fargate with CI/CD.'
    }
    assert errors_only(validate_patch(master, policy, good_patch)) == []  # no digits, so the number rule stays quiet
    v = apply_patch(master, good_patch)
    r = render(v, tmp_path / "i.pdf", page_limit=1)
    assert r.ok, r.errors  # rendered literally, no code ran


def test_baseline_patch_is_valid(master, policy):
    p = baseline_patch(master, policy, JD.read_text())
    assert errors_only(validate_patch(master, policy, p)) == []
    assert "sk-claude" in p.skills[:10] or "sk-mcp" in p.skills[:10]


def test_diff_reports_changes(master, good_patch):
    v = apply_patch(master, good_patch)
    d = diff(master, v, good_patch)
    assert d["sections"]["exp-acme-sde"]["dropped"] == ["exp-acme-sde-feperf", "exp-acme-sde-prefetch"]
    assert d["sections"]["prj-tailorlock"]["status"] == "dropped"
    assert "SECTION exp-acme-sde" in format_diff(d)


def test_run_tailor_baseline_end_to_end(tmp_path):
    store = Store(tmp_path / "t.db")
    res = run_tailor(JD, BaselineProvider(), max_attempts=2, master_path=EXAMPLE, out_dir=tmp_path / "out", store=store)
    assert res.ok, res.summary()
    assert res.pdf_path and res.pdf_path.exists()
    runs = store.list_runs()
    assert len(runs) == 1 and runs[0]["status"] == "ok" and runs[0]["pages"] == 1
    json.loads((tmp_path / "out" / "nordavo-agentic-ai-engineer.patch.json").read_text())


def test_feedback_loop_retries_on_invalid_patch(master, policy, tmp_path):
    from tailorlock.cost import Usage
    from tailorlock.schema import Patch, SectionPatch

    class FlakyProvider:
        name = "flaky"; model = "baseline"
        def __init__(self): self.seen_feedback = []
        def propose(self, master, policy, jd, feedback):
            self.seen_feedback.append(list(feedback))
            if not feedback:
                return Patch(sections={"exp-acme-sde": SectionPatch(include=["exp-acme-sde-pay"], rewrites={"exp-acme-sde-pay": "Saved 99%."})}), Usage(calls=1)
            return baseline_patch(master, policy, jd), Usage(calls=1)

    prov = FlakyProvider()
    res = run_tailor(JD, prov, max_attempts=3, master_path=EXAMPLE, out_dir=tmp_path / "out", store=Store(tmp_path / "t.db"))
    assert res.ok and len(res.attempts) == 2
    assert res.attempts[0].status == "invalid"
    assert any("new_number" in f for f in prov.seen_feedback[1])


def test_projects_follow_patch_order(master, good_patch):
    from tailorlock.schema import SectionPatch
    good_patch.sections = {
        "prj-tailorlock": SectionPatch(include=["prj-tailorlock-mcp", "prj-tailorlock-gate"]),
        **{k: v for k, v in good_patch.sections.items()},
    }
    v = apply_patch(master, good_patch)
    assert [p.id for p in v.projects] == ["prj-tailorlock", "prj-mentor"]
