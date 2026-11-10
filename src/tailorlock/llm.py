"""Anthropic provider. The model sees the master (with ids), the policy and the
job description, and must return a Patch. Structured outputs guarantee the
shape; validate.py decides whether the content is acceptable.

Cost hygiene:
  * system prompt + master + policy are the stable prefix and get cache_control;
    only the JD and validator feedback vary per request.
  * one call per attempt; the pipeline caps attempts.
"""
from __future__ import annotations

import json

import anthropic

from .cost import Usage
from .schema import Patch, Policy, Resume

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM = """You tailor a resume to a job description by producing a PATCH, nothing else.

You may ONLY:
  * choose which existing bullets to keep per role/project, and their order;
  * rewrite kept bullets (same facts, sharper wording, mirror the JD's vocabulary); keep key numbers
    wrapped in **double asterisks** so they render bold, as the master does;
  * reword a bullet's bold lead-in label via `relabel` (e.g. "Asynchronous Notifications" -> "Event-Driven Processing");
  * choose an ordered subset of the existing skills;
  * rewrite the summary paragraph (and the title only if the policy allows one).

You may NEVER:
  * invent a bullet, skill, employer, date, or number that is not in the master;
  * move a bullet to a different role;
  * change anything not listed above. The patch format has no field for it; do not try.

Writing rules (the validator enforces these, so follow them the first time):
  * every number in a rewritten bullet must already appear in that bullet's original text;
  * respect the character limits and per-section bullet counts in the policy;
  * no first person, no forbidden phrases, no weak openers; start bullets with a strong verb;
  * the whole resume must fit on one page, so prefer fewer, denser bullets.

Think about what the hiring team actually asks for and lead with the evidence that answers it.
If you receive validator feedback, fix exactly what it names and keep everything else."""


def _user_message(master: Resume, policy: Policy, jd_text: str, feedback: list[str]) -> list[dict]:
    blocks = [
        {
            "type": "text",
            "text": "MASTER RESUME (yaml, with ids):\n" + json.dumps(master.model_dump(mode="json"), indent=1, ensure_ascii=False),
        },
        {
            "type": "text",
            "text": "POLICY:\n" + json.dumps(policy.model_dump(mode="json"), indent=1),
            # Everything up to here is identical across jobs -> cache it.
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": "JOB DESCRIPTION:\n" + jd_text},
    ]
    if feedback:
        blocks.append({"type": "text", "text": "VALIDATOR FEEDBACK on your previous patch. Fix these:\n- " + "\n- ".join(feedback)})
    blocks.append({"type": "text", "text": "Return the patch now."})
    return blocks


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = "medium", fallbacks: bool = True):
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks
        self.client = anthropic.Anthropic()

    def propose(self, master: Resume, policy: Policy, jd_text: str, feedback: list[str]) -> tuple[Patch, Usage]:
        kwargs: dict = dict(
            model=self.model,
            max_tokens=8000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": _user_message(master, policy, jd_text, feedback)}],
            output_format=Patch,
            output_config={"effort": self.effort},
        )
        if self.fallbacks:
            # Server-side refusal fallback: if a safety classifier declines, the API
            # re-runs on a fallback model inside the same call.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        resp = self.client.beta.messages.parse(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        u = resp.usage
        usage = Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            calls=1,
        )
        patch = resp.parsed_output
        if patch is None:
            raise RuntimeError("model returned no parsable patch")
        return patch, usage
