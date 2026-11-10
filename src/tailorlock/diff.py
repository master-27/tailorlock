"""Human-readable diff between the master and a variant: exactly which
whitelisted fields changed, so a reviewer can approve in under a minute."""
from __future__ import annotations

from .schema import Patch, Resume


def diff(master: Resume, variant: Resume, patch: Patch | None = None) -> dict:
    out: dict = {"title": None, "summary": None, "skills": None, "sections": {}}

    if master.basics.title != variant.basics.title:
        out["title"] = {"before": master.basics.title, "after": variant.basics.title}
    if master.summary.strip() != variant.summary.strip():
        out["summary"] = {"before": master.summary, "after": variant.summary}

    m_sk = [s.id for s in master.skills]
    v_sk = [s.id for s in variant.skills]
    if m_sk != v_sk:
        out["skills"] = {
            "shown": v_sk,
            "dropped": [s for s in m_sk if s not in v_sk],
            "reordered": [s for s in v_sk if s in m_sk] != [s for s in m_sk if s in v_sk],
        }

    for m_sec in list(master.experience) + list(master.projects):
        v_sec = variant.section(m_sec.id)
        m_ids = [b.id for b in m_sec.bullets]
        if v_sec is None:
            out["sections"][m_sec.id] = {"status": "dropped", "dropped": m_ids}
            continue
        v_by = {b.id: b.text for b in v_sec.bullets}
        m_by = {b.id: b.text for b in m_sec.bullets}
        kept = [b.id for b in v_sec.bullets]
        rewritten = {bid: {"before": m_by[bid], "after": v_by[bid]} for bid in kept if m_by.get(bid, "").strip() != v_by[bid].strip()}
        dropped = [b for b in m_ids if b not in v_by]
        if kept != m_ids or rewritten or dropped:
            out["sections"][m_sec.id] = {"status": "changed", "kept_in_order": kept, "dropped": dropped, "rewritten": rewritten}

    if patch is not None and patch.rationale:
        out["rationale"] = patch.rationale
    return out


def format_diff(d: dict) -> str:
    lines: list[str] = []
    if d.get("title"):
        lines += ["TITLE", f"  - {d['title']['before']}", f"  + {d['title']['after']}"]
    if d.get("summary"):
        lines += ["SUMMARY", f"  - {d['summary']['before'].strip()}", f"  + {d['summary']['after'].strip()}"]
    if d.get("skills"):
        s = d["skills"]
        lines += ["SKILLS", f"  shown ({len(s['shown'])}): {', '.join(s['shown'])}"]
        if s["dropped"]:
            lines.append(f"  dropped: {', '.join(s['dropped'])}")
    for sid, sec in d.get("sections", {}).items():
        lines.append(f"SECTION {sid} [{sec['status']}]")
        if sec.get("kept_in_order"):
            lines.append(f"  kept: {', '.join(sec['kept_in_order'])}")
        if sec.get("dropped"):
            lines.append(f"  dropped: {', '.join(sec['dropped'])}")
        for bid, rw in sec.get("rewritten", {}).items():
            lines += [f"  ~ {bid}", f"    - {rw['before'].strip()}", f"    + {rw['after'].strip()}"]
    if d.get("rationale"):
        lines += ["RATIONALE", f"  {d['rationale'].strip()}"]
    return "\n".join(lines) if lines else "(no changes)"
