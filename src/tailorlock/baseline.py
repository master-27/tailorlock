"""Deterministic baseline provider: no LLM.

Ranks bullets by keyword overlap with the job description, keeps the top N
per role within policy, reorders skills by how often the JD mentions them,
and leaves title/summary untouched. Two uses:
  1. evals - a floor the LLM must beat;
  2. a starting point the agent can refine instead of starting from nothing.
"""
from __future__ import annotations

import re

from .cost import Usage
from .keywords import extract_keywords
from .schema import Patch, Policy, Resume, SectionPatch


def _score(text: str, keywords: list[str]) -> float:
    low = text.lower()
    return sum(1.0 / (1 + i * 0.05) for i, k in enumerate(keywords) if k in low)


def baseline_patch(master: Resume, policy: Policy, jd_text: str) -> Patch:
    kws = extract_keywords(jd_text, top=40)
    bp = policy.editable.bullets

    sections: dict[str, SectionPatch] = {}
    for e in master.experience:
        ranked = sorted(e.bullets, key=lambda b: _score(b.text, kws), reverse=True)
        keep = ranked[: bp.max_per_role]
        # keep master order for readability
        order = [b.id for b in e.bullets if b in keep]
        sections[e.id] = SectionPatch(include=order)

    proj_scores = [(p, max((_score(b.text, kws) for b in p.bullets), default=0.0)) for p in master.projects]
    proj_scores.sort(key=lambda t: t[1], reverse=True)
    for p, _ in proj_scores[: bp.max_projects]:
        ranked = sorted(p.bullets, key=lambda b: _score(b.text, kws), reverse=True)[: bp.max_per_project]
        sections[p.id] = SectionPatch(include=[b.id for b in p.bullets if b in ranked])

    jd_low = jd_text.lower()
    def skill_hits(name: str) -> int:
        tokens = [t for t in re.split(r"[\s/(),]+", name.lower()) if len(t) > 2]
        return sum(jd_low.count(t) for t in tokens)
    ranked_skills = sorted(master.skills, key=lambda s: skill_hits(s.name), reverse=True)
    n = max(policy.editable.skills.min_count, min(policy.editable.skills.max_count, len(master.skills)))
    skills = [s.id for s in ranked_skills[:n]]

    return Patch(skills=skills, sections=sections, rationale="baseline: keyword-overlap ranking, no rewrites")


class BaselineProvider:
    name = "baseline"
    model = "baseline"

    def propose(self, master: Resume, policy: Policy, jd_text: str, feedback: list[str]) -> tuple[Patch, Usage]:
        return baseline_patch(master, policy, jd_text), Usage(calls=1)
