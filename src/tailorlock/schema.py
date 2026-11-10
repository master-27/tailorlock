"""Data model for the master resume, the policy, and the patch the AI may propose.

Three layers:
  * Resume  - the master, owned by the human. Every bullet has a stable id.
  * Policy  - what the AI may change and within which limits.
  * Patch   - the ONLY thing the AI produces. It can reference ids, select,
              reorder and rewrite; it has no field for anything that is locked.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- master resume
class Link(Strict):
    label: str
    url: str


class Basics(Strict):
    name: str
    title: str
    email: str
    phone: str
    location: str
    links: list[Link] = []


class Skill(Strict):
    id: str
    name: str
    group: str


class Bullet(Strict):
    id: str
    text: str
    label: str = ""  # bold lead-in rendered as "Label:" before the text; "" = none


class Experience(Strict):
    id: str
    company: str
    role: str
    location: str = ""
    start: str
    end: str
    bullets: list[Bullet]


class Project(Strict):
    id: str
    name: str
    subtitle: str = ""
    stack: str = ""
    link: str = ""
    bullets: list[Bullet]


class Education(Strict):
    id: str
    institution: str
    degree: str
    location: str = ""
    start: str | int
    end: str | int
    coursework: str = ""


class Resume(Strict):
    basics: Basics
    summary: str
    skills: list[Skill]
    experience: list[Experience]
    projects: list[Project] = []
    education: list[Education] = []

    def skill_ids(self) -> set[str]:
        return {s.id for s in self.skills}

    def section(self, section_id: str) -> Experience | Project | None:
        for e in self.experience:
            if e.id == section_id:
                return e
        for p in self.projects:
            if p.id == section_id:
                return p
        return None

    def bullet(self, section_id: str, bullet_id: str) -> Bullet | None:
        sec = self.section(section_id)
        if sec is None:
            return None
        for b in sec.bullets:
            if b.id == bullet_id:
                return b
        return None

    def plain_text(self) -> str:
        """All visible text, used for keyword coverage scoring."""
        parts = [self.basics.title, self.summary]
        parts += [s.name for s in self.skills]
        for e in self.experience:
            parts += [e.role, e.company] + [f"{b.label} {b.text}" for b in e.bullets]
        for p in self.projects:
            parts += [p.name, p.stack] + [b.text for b in p.bullets]
        return "\n".join(parts)


# ---------------------------------------------------------------------- policy
class TitlePolicy(Strict):
    max_chars: int = 60  # 0 disables the title entirely (layout has no title line)


class SummaryPolicy(Strict):
    min_chars: int = 100
    max_chars: int = 400


class SkillsPolicy(Strict):
    min_count: int = 6
    max_count: int = 16


class BulletsPolicy(Strict):
    rewrite: bool = True
    relabel: bool = True
    label_max_chars: int = 40
    max_chars: int = 210
    min_per_role: int = 2
    max_per_role: int = 4
    min_per_project: int = 1
    max_per_project: int = 2
    max_projects: int = 2


class Editable(Strict):
    title: TitlePolicy = TitlePolicy()
    summary: SummaryPolicy = SummaryPolicy()
    skills: SkillsPolicy = SkillsPolicy()
    bullets: BulletsPolicy = BulletsPolicy()


class Rules(Strict):
    no_new_numbers: bool = True
    forbidden_phrases: list[str] = []
    forbidden_starters: list[str] = []
    no_first_person: bool = True


class Policy(Strict):
    page_limit: int = 1
    editable: Editable = Editable()
    rules: Rules = Rules()


# ----------------------------------------------------- patch: the AI's output
class SectionPatch(Strict):
    """Selection, order and rewrites for one experience or project section."""

    include: list[str] = Field(
        description="Ordered bullet ids from this section to keep. Omitted bullets are dropped."
    )
    rewrites: dict[str, str] = Field(
        default_factory=dict,
        description="bullet id -> new text. Only ids present in `include`. Any number must already exist in the original bullet. Wrap key numbers in **double asterisks** to bold them, as the master does.",
    )
    relabel: dict[str, str] = Field(
        default_factory=dict,
        description="bullet id -> new bold lead-in label (without the colon). Only for bullets that already have a label.",
    )


class Patch(Strict):
    title: str | None = Field(default=None, description="New headline title, or null to keep the master's.")
    summary: str | None = Field(default=None, description="New summary paragraph, or null to keep the master's.")
    skills: list[str] | None = Field(
        default=None, description="Ordered subset of existing skill ids to show. Null keeps the master list."
    )
    sections: dict[str, SectionPatch] = Field(
        default_factory=dict,
        description="experience/project id -> selection. Roles not listed keep all bullets; projects not listed are dropped; projects render in the order listed here.",
    )
    rationale: str = Field(default="", description="One short paragraph: why these choices for this job.")


# --------------------------------------------------------------------- loaders
def load_yaml(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_resume(path: Path | str) -> Resume:
    return Resume.model_validate(load_yaml(path))


def load_policy(path: Path | str) -> Policy:
    return Policy.model_validate(load_yaml(path))


Severity = Literal["error", "warning"]


class Issue(Strict):
    severity: Severity = "error"
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} @ {self.path}: {self.message}"
