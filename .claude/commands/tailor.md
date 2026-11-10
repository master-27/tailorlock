---
description: Tailor the master resume to a job description, within policy, and show the diff for approval.
argument-hint: <path to job description .md> [note]
allowed-tools: mcp__tailorlock__*, Read, Agent
---
Tailor the resume for the job description at `$ARGUMENTS`.

You are operating under the resume-rules skill. The layout, the policy and the
master are locked; you only produce a patch. Follow this exact loop:

1. Call `mcp__tailorlock__get_job` with the path to read the JD, then
   `mcp__tailorlock__get_master` and `mcp__tailorlock__get_policy`.
2. Delegate JD analysis to the `jd-analyst` subagent (pass it the JD text).
   It returns: must-have themes, nice-to-haves, and the vocabulary the hiring
   team uses. Do not skip this; it keeps the JD out of your main context twice.
3. Optionally call `mcp__tailorlock__baseline_patch` to get a keyword-ranked
   starting point. Improve on it; do not just return it.
4. Draft the patch (JSON matching the Patch schema from `get_policy`), then
   call `mcp__tailorlock__render_patch`. It validates, renders to PDF, checks
   the page limit and logs the run. If it returns errors, fix exactly those
   and call it again. Max 3 rounds. Never work around an error by touching
   files; the guard hook will block you anyway.
5. When it passes, send the diff and the JD themes to the `resume-critic`
   subagent for one review pass. Apply its concrete suggestions if they are
   within policy, re-render once.
6. Report to the user: the run id, pages, cost, the diff (from the tool's
   `diff_text`), and the PDF path. Ask for approval before anything else.
   You own the result; the model proposed it, you checked it.
