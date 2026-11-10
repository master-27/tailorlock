"""Validate a Patch against the master Resume and the Policy.

Every check here is deterministic and cheap. The point is that the model
does not get to decide whether its own output is acceptable; this does.
"""
from __future__ import annotations

import re

from .schema import Experience, Issue, Patch, Policy, Project, Resume

_NUM = re.compile(r"\d[\d,.]*")


def _numbers(text: str) -> set[str]:
    return {n.strip(",.") for n in _NUM.findall(text)}


def _text_rules(text: str, path: str, policy: Policy, issues: list[Issue]) -> None:
    low = text.lower()
    for phrase in policy.rules.forbidden_phrases:
        if phrase.lower() in low:
            issues.append(Issue(code="forbidden_phrase", path=path, message=f"contains forbidden phrase '{phrase}'"))
    if policy.rules.no_first_person and re.search(r"\b(I|my|me|we|our)\b", text):
        issues.append(Issue(code="first_person", path=path, message="uses first-person pronoun"))


def _check_bullet(
    section: Experience | Project, bid: str, new_text: str, policy: Policy, issues: list[Issue]
) -> None:
    path = f"sections.{section.id}.rewrites.{bid}"
    original = next((b for b in section.bullets if b.id == bid), None)
    if original is None:
        issues.append(Issue(code="unknown_bullet", path=path, message=f"bullet id '{bid}' not in section '{section.id}'"))
        return
    if not policy.editable.bullets.rewrite and new_text.strip() != original.text.strip():
        issues.append(Issue(code="rewrite_forbidden", path=path, message="policy forbids rewriting bullets"))
    if not new_text.strip():
        issues.append(Issue(code="empty", path=path, message="rewritten bullet is empty"))
        return
    visible = len(new_text.replace("**", ""))
    if visible > policy.editable.bullets.max_chars:
        issues.append(
            Issue(code="too_long", path=path, message=f"{visible} chars > max {policy.editable.bullets.max_chars}")
        )
    if new_text.count("**") % 2 == 1:
        issues.append(Issue(code="unbalanced_bold", path=path, message="odd number of ** markers"))
    if policy.rules.no_new_numbers:
        new_nums = _numbers(new_text) - _numbers(original.text)
        if new_nums:
            issues.append(
                Issue(
                    code="new_number",
                    path=path,
                    message=f"introduces numbers not in the original bullet: {sorted(new_nums)}",
                )
            )
    first_word = new_text.strip().split(" ", 1)[0].rstrip(",.:;")
    for starter in policy.rules.forbidden_starters:
        if new_text.strip().lower().startswith(starter.lower() + " ") or first_word.lower() == starter.lower():
            issues.append(Issue(code="weak_starter", path=path, message=f"starts with '{starter}'"))
    _text_rules(new_text, path, policy, issues)


def _check_section(
    section: Experience | Project, include: list[str], rewrites: dict[str, str], relabel: dict[str, str],
    policy: Policy, issues: list[Issue], is_role: bool
) -> None:
    path = f"sections.{section.id}"
    valid_ids = {b.id for b in section.bullets}
    seen: set[str] = set()
    for bid in include:
        if bid not in valid_ids:
            issues.append(Issue(code="unknown_bullet", path=f"{path}.include", message=f"'{bid}' is not a bullet of '{section.id}'"))
        if bid in seen:
            issues.append(Issue(code="duplicate_bullet", path=f"{path}.include", message=f"'{bid}' listed twice"))
        seen.add(bid)
    for bid in rewrites:
        if bid not in include:
            issues.append(Issue(code="rewrite_not_included", path=f"{path}.rewrites.{bid}", message="rewritten bullet is not in `include`"))
    for bid, new_label in relabel.items():
        lpath = f"{path}.relabel.{bid}"
        orig = next((b for b in section.bullets if b.id == bid), None)
        if orig is None:
            issues.append(Issue(code="unknown_bullet", path=lpath, message=f"'{bid}' is not a bullet of '{section.id}'"))
            continue
        if bid not in include:
            issues.append(Issue(code="relabel_not_included", path=lpath, message="relabelled bullet is not in `include`"))
        if not policy.editable.bullets.relabel:
            issues.append(Issue(code="relabel_forbidden", path=lpath, message="policy forbids changing labels"))
        if not orig.label:
            issues.append(Issue(code="label_not_allowed", path=lpath, message="this bullet has no label in the master; labels cannot be added"))
        if len(new_label) > policy.editable.bullets.label_max_chars:
            issues.append(Issue(code="too_long", path=lpath, message=f"label {len(new_label)} chars > max {policy.editable.bullets.label_max_chars}"))
        if ":" in new_label:
            issues.append(Issue(code="label_colon", path=lpath, message="label must not contain ':' (the template adds it)"))
        _text_rules(new_label, lpath, policy, issues)
    bp = policy.editable.bullets
    lo, hi = (bp.min_per_role, bp.max_per_role) if is_role else (bp.min_per_project, bp.max_per_project)
    n = len([b for b in include if b in valid_ids])
    if n < lo:
        issues.append(Issue(code="too_few_bullets", path=path, message=f"{n} bullets < min {lo}"))
    if n > hi:
        issues.append(Issue(code="too_many_bullets", path=path, message=f"{n} bullets > max {hi}"))
    for bid, text in rewrites.items():
        if bid in valid_ids:
            _check_bullet(section, bid, text, policy, issues)


def validate_patch(master: Resume, policy: Policy, patch: Patch) -> list[Issue]:
    issues: list[Issue] = []

    # title
    if patch.title is not None:
        if policy.editable.title.max_chars == 0:
            issues.append(Issue(code="title_disabled", path="title", message="this layout has no title line; leave title null"))
        elif not patch.title.strip():
            issues.append(Issue(code="empty", path="title", message="title is empty"))
        elif len(patch.title) > policy.editable.title.max_chars:
            issues.append(Issue(code="too_long", path="title", message=f"{len(patch.title)} chars > max {policy.editable.title.max_chars}"))
        _text_rules(patch.title or "", "title", policy, issues)

    # summary
    if patch.summary is not None:
        n = len(patch.summary.strip().replace("**", ""))
        sp = policy.editable.summary
        if n < sp.min_chars:
            issues.append(Issue(code="too_short", path="summary", message=f"{n} chars < min {sp.min_chars}"))
        if n > sp.max_chars:
            issues.append(Issue(code="too_long", path="summary", message=f"{n} chars > max {sp.max_chars}"))
        if policy.rules.no_new_numbers:
            allowed = _numbers(master.summary) | {n_ for e in master.experience for b in e.bullets for n_ in _numbers(b.text)}
            new_nums = _numbers(patch.summary) - allowed
            if new_nums:
                issues.append(Issue(code="new_number", path="summary", message=f"introduces numbers not found anywhere in the master: {sorted(new_nums)}"))
        _text_rules(patch.summary, "summary", policy, issues)

    # skills
    if patch.skills is not None:
        known = master.skill_ids()
        seen: set[str] = set()
        for sid in patch.skills:
            if sid not in known:
                issues.append(Issue(code="unknown_skill", path="skills", message=f"'{sid}' is not a skill id in the master"))
            if sid in seen:
                issues.append(Issue(code="duplicate_skill", path="skills", message=f"'{sid}' listed twice"))
            seen.add(sid)
        n = len([s for s in patch.skills if s in known])
        kp = policy.editable.skills
        if n < kp.min_count:
            issues.append(Issue(code="too_few_skills", path="skills", message=f"{n} skills < min {kp.min_count}"))
        if n > kp.max_count:
            issues.append(Issue(code="too_many_skills", path="skills", message=f"{n} skills > max {kp.max_count}"))

    # sections
    exp_ids = {e.id for e in master.experience}
    proj_ids = {p.id for p in master.projects}
    for sid, sp in patch.sections.items():
        section = master.section(sid)
        if section is None:
            issues.append(Issue(code="unknown_section", path=f"sections.{sid}", message="not an experience or project id in the master"))
            continue
        _check_section(section, sp.include, sp.rewrites, sp.relabel, policy, issues, is_role=sid in exp_ids)

    n_proj = len([s for s in patch.sections if s in proj_ids])
    if n_proj > policy.editable.bullets.max_projects:
        issues.append(Issue(code="too_many_projects", path="sections", message=f"{n_proj} projects > max {policy.editable.bullets.max_projects}"))

    # roles the patch did not touch still have to respect max_per_role
    for e in master.experience:
        if e.id not in patch.sections and len(e.bullets) > policy.editable.bullets.max_per_role:
            issues.append(
                Issue(
                    severity="warning",
                    code="untouched_role_too_long",
                    path=f"sections.{e.id}",
                    message=f"role not in patch keeps all {len(e.bullets)} bullets (> max {policy.editable.bullets.max_per_role}); select a subset",
                )
            )

    return issues


def errors_only(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]
