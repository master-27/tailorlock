---
name: resume-rules
description: How to tailor a resume inside tailorlock. Use whenever asked to tailor, adapt, rewrite or target a resume to a job description, or when the tailorlock MCP tools are in play.
---
# Resume tailoring rules (tailorlock)

## The contract
- The **template** (`template/resume.typ`) and **policy** (`data/policy.yaml`) are locked. Never edit them. A hook blocks it; do not try to route around the hook.
- The **master** (`data/master.yaml`) is the only source of facts. Never add facts that are not in it.
- Your whole output is a **Patch**: selected bullet ids per section, optional rewrites, an ordered subset of skill ids, optional title and summary. Nothing else exists.

## How to choose
1. Read the JD for what the team is actually judging: the first three bullets under "what you'll do" and "skills we look for" carry most of the weight.
2. Lead each role with the bullet that answers the JD's biggest ask. Order inside a role is by relevance, not chronology.
3. Prefer bullets with evidence (numbers, named tools, outcomes) over bullets that describe duties.
4. Mirror the JD's vocabulary when the master supports it (if they say "MCP servers" and the master has MCP servers, say "MCP servers"). Never claim a tool that is not in the master.
5. Skills: show the ones the JD mentions first, then the strongest adjacent ones. Drop the irrelevant rest; a shorter list reads stronger.

## Owner-specific rules (from the resume bank)
- Farmart backend used both Spring Boot and Node.js. Spring/Java JDs: frame Farmart work as Java/Spring Boot and lead with Java in skills. Node/Go JDs: frame as Node.js/Go. Both are true; pick one framing per resume.
- Never list Next.js or Redux (policy forbids the words).
- The AI Mentorship project is Node.js + Express. Do not call it Spring Boot.
- Owner has ~1.5 years full-time plus internships. Do not inflate seniority in the summary.

## How to rewrite
- Each experience bullet has a bold lead-in `label` ("Payments & Reconciliation"). You may reword it with `relabel` to the JD's vocabulary; never add a label to a bullet that has none.
- Keep key numbers wrapped in `**double asterisks**`; the template bolds them, as the owner's resumes do.
- Same facts, sharper verb, JD vocabulary. Every number must already be in the original bullet.
- Start with a verb. No "Responsible for", no "Helped", no first person.
- Length limits are in the policy. One page is a hard limit, so when in doubt cut a bullet rather than shrinking three.
- Summary: who they are, how long, the two or three things this JD cares about most, in that order.

## How to fix validator feedback
- Fix exactly what the message names. Do not reshuffle everything else.
- `new_number`: remove the number or use the one from the original bullet.
- `page_overflow`: drop the lowest-relevance bullet first, then shorten.
- `too_many_bullets` / `too_few_bullets`: the counts are policy; adjust `include`.

## Done means
- `render_patch` returned `ok: true`, pages within limit.
- The diff is readable and every change has a reason tied to the JD.
- A human approves before the PDF is sent anywhere.
