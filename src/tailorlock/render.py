"""Render a Resume variant to PDF with the locked Typst template and check it
against the page limit. Deterministic; no model involved."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import typst
from pypdf import PdfReader

from . import paths
from .schema import Resume


@dataclass
class RenderResult:
    ok: bool
    pdf_path: Path | None
    pages: int
    seconds: float
    errors: list[str] = field(default_factory=list)


_SPECIALS = "\\#$*_`<>@~"


def to_markup(text: str) -> str:
    """Escape everything Typst would interpret, then re-enable **bold** only.

    The model's text goes through eval(mode: "markup") in the template, so this
    is the line between 'bold a number' and 'run code in the renderer'."""
    out = []
    for ch in text:
        out.append("\\" + ch if ch in _SPECIALS else ch)
    s = "".join(out).replace("//", "\\/\\/").replace("--", "-\\-")
    return re.sub(r"\\\*\\\*(.+?)\\\*\\\*", r"*\1*", s)


def _prepare(variant: Resume) -> dict:
    data = variant.model_dump(mode="json")
    data["summary"] = to_markup(data["summary"])
    for sec in data["experience"] + data["projects"]:
        for b in sec["bullets"]:
            b["text"] = to_markup(b["text"])
            b["label"] = to_markup(b.get("label", "")).replace("*", "")  # labels are already bold
    return data


def count_pages(pdf: Path) -> int:
    return len(PdfReader(str(pdf)).pages)


def render(variant: Resume, out_pdf: Path, page_limit: int = 1, template: Path | None = None) -> RenderResult:
    template = template or paths.TEMPLATE
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_prepare(variant), ensure_ascii=False)
    t0 = time.perf_counter()
    try:
        typst.compile(str(template), output=str(out_pdf), sys_inputs={"data": data})
    except Exception as exc:  # typst raises a plain RuntimeError with the diagnostics
        return RenderResult(ok=False, pdf_path=None, pages=0, seconds=time.perf_counter() - t0, errors=[f"typst: {exc}"])
    pages = count_pages(out_pdf)
    errors: list[str] = []
    if pages > page_limit:
        errors.append(f"page_overflow: rendered {pages} pages, limit is {page_limit}. Shorten bullets or include fewer.")
    return RenderResult(ok=not errors, pdf_path=out_pdf, pages=pages, seconds=time.perf_counter() - t0, errors=errors)
