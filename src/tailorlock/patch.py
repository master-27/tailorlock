"""Apply a Patch to the master Resume to produce a variant.

This is deliberately dumb: no judgement, no LLM. It only does what the patch
says and what the policy structurally allows. validate.py decides whether the
patch is acceptable; this module assumes it already passed.
"""
from __future__ import annotations

from .schema import Bullet, Experience, Patch, Project, Resume


def _select_bullets(
    section: Experience | Project, include: list[str], rewrites: dict[str, str], relabel: dict[str, str]
) -> list[Bullet]:
    by_id = {b.id: b for b in section.bullets}
    out: list[Bullet] = []
    for bid in include:
        if bid not in by_id:  # validator should have caught this; skip defensively
            continue
        text = rewrites.get(bid, by_id[bid].text)
        label = relabel.get(bid, by_id[bid].label)
        out.append(Bullet(id=bid, text=text.strip(), label=label.strip()))
    return out


def apply_patch(master: Resume, patch: Patch) -> Resume:
    variant = master.model_copy(deep=True)

    if patch.title is not None:
        variant.basics.title = patch.title.strip()
    if patch.summary is not None:
        variant.summary = patch.summary.strip()

    if patch.skills is not None:
        by_id = {s.id: s for s in master.skills}
        variant.skills = [by_id[sid] for sid in patch.skills if sid in by_id]

    # Experience: roles are never dropped or reordered; only their bullets change.
    new_exp: list[Experience] = []
    for exp in master.experience:
        sp = patch.sections.get(exp.id)
        e = exp.model_copy(deep=True)
        if sp is not None:
            e.bullets = _select_bullets(exp, sp.include, sp.rewrites, sp.relabel)
        new_exp.append(e)
    variant.experience = new_exp

    # Projects: only the ones the patch mentions are shown, in the order the
    # patch lists them (so the agent can lead with the most relevant project).
    by_id = {p.id: p for p in master.projects}
    new_proj: list[Project] = []
    for sid, sp in patch.sections.items():
        proj = by_id.get(sid)
        if proj is None:
            continue
        p = proj.model_copy(deep=True)
        p.bullets = _select_bullets(proj, sp.include, sp.rewrites, sp.relabel)
        new_proj.append(p)
    variant.projects = new_proj

    return variant
