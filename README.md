# TailorLock

A resume tailor where the AI is allowed to change **only** what the resume owner whitelisted.

The layout, the section order, the employers, the dates and the rules are locked. The agent
proposes a *patch*: which bullets to keep, in what order, how to reword them, which skills to
show, and a new title and summary. A validator and a Typst renderer gate every patch. If the
patch invents a number, breaks a length limit, or pushes the resume onto a second page, it is
rejected with a precise error and the agent gets to try again. Every attempt is logged.

Built as a Claude Code project: an MCP server, a guard hook, a skill, a custom command and two
subagents. The agent is Claude Code itself; the Python code is the harness around it.

```
                 locked (owner)                       the AI's whole output surface
   ┌──────────────────────────────────┐          ┌──────────────────────────────────┐
   │ template/resume.typ   (layout)   │          │ Patch                            │
   │ data/policy.yaml      (rules)    │          │   title?  summary?  skills[]?    │
   │ data/master.yaml      (facts)    │          │   sections{id: include[], rewrites{}} │
   └──────────────┬───────────────────┘          └──────────────┬───────────────────┘
                  │                                              │
                  ▼                                              ▼
          validate_patch()  ──errors──▶ back to the agent   (max 3 rounds)
                  │ ok
                  ▼
          apply_patch() ──▶ render() with Typst ──▶ page count ≤ limit? ──no──▶ back to the agent
                  │ yes
                  ▼
          PDF + diff + audit row in SQLite
```

## Why this shape

Most "AI resume" tools hand the model a LaTeX or Word file and hope. The model then helpfully
"improves" the margins, drops a date, or rounds 2.1% up to 5%. TailorLock fixes that by
construction rather than by prompt:

| Problem | Where it is solved |
|---|---|
| Model edits the layout | It never sees the template. The patch schema has no field for it. A PreToolUse hook blocks `Edit`/`Write`/`Bash` writes to `template/`, `data/policy.yaml` and the hooks themselves. |
| Model invents metrics | `no_new_numbers`: every digit in a rewritten bullet must already exist in the original bullet. |
| Model pads the resume onto page 2 | Renderer counts pages; overflow is an error fed back to the agent. |
| Model moves a bullet between jobs | Bullets are addressed by `section id + bullet id`; the validator rejects unknown pairs. |
| Nobody can see what changed | `diff_text` lists exactly which fields changed, before and after. |
| No idea what it cost | Every run is a row in `.tailorlock.db` with tokens, cache hits and USD. |

## Layout

```
tailorlock/
├── template/resume.typ          LOCKED  Typst layout; reads JSON from sys.inputs
├── data/policy.yaml             LOCKED  what the AI may change, within what limits
├── data/master.yaml             GITIGNORED  the owner's facts; every bullet/skill has a stable id
├── data/master.example.yaml             fictional persona with the same shape, for demos/tests
├── jobs/*.md                            4 real JDs: Nordavo (agentic), Uplers (Java/Spring), Axionix (Node), Ruloans (full-stack)
├── src/tailorlock/
│   ├── schema.py                Pydantic: Resume, Policy, Patch (extra="forbid" everywhere)
│   ├── validate.py              deterministic checks -> list[Issue]
│   ├── patch.py                 apply a Patch to the master -> variant
│   ├── render.py                Typst compile + page count
│   ├── diff.py                  field-level before/after
│   ├── baseline.py              keyword-overlap provider, no LLM (eval floor + starting point)
│   ├── llm.py                   Anthropic provider: structured output, prompt caching, fallbacks
│   ├── tailor.py                propose -> validate -> render -> retry loop
│   ├── store.py                 SQLite audit log
│   ├── cost.py                  token -> USD
│   ├── keywords.py              JD keyword extraction + coverage score
│   ├── mcp_server.py            the only door for the agent
│   └── cli.py
├── .mcp.json                    registers the MCP server with Claude Code
├── .claude/
│   ├── settings.json            hooks wiring
│   ├── hooks/guard-locked-files.sh   PreToolUse: block writes to the locked layer (exit 2)
│   ├── hooks/log-tool-call.sh        PostToolUse: audit every tailorlock MCP call
│   ├── commands/tailor.md       /tailor <jd.md>  the orchestrated flow
│   ├── skills/resume-rules/     how to choose, rewrite and fix validator feedback
│   └── agents/jd-analyst.md, resume-critic.md   subagents (haiku / sonnet)
├── evals/                       the same 4 JDs, expectations, run_evals.py
└── tests/                       40 tests incl. hook payload and markup-injection tests, ~3 s
```

## Quick start

```bash
uv sync --all-groups
cp data/master.example.yaml data/master.yaml       # or write your own; see "Data files"
uv run pytest -q                                   # 40 passed (tests use the example persona)
uv run tailorlock render                           # render the untouched master
uv run tailorlock tailor jobs/nordavo-agentic-ai-engineer.md --provider baseline --diff
uv run tailorlock runs                             # audit log
```

### Inside Claude Code (the intended path)

```bash
cd tailorlock && claude
> /tailor jobs/nordavo-agentic-ai-engineer.md
```

The command runs: `get_job` -> `jd-analyst` subagent -> `get_master`/`get_policy` ->
optional `baseline_patch_for` -> draft -> `render_patch` (validate + render + log) ->
fix exactly the reported errors, max 3 rounds -> `resume-critic` subagent -> report the
diff, pages, run id and PDF path, then wait for human approval.

Headless, the same flow:

```bash
claude -p "/tailor jobs/nordavo-agentic-ai-engineer.md" --mcp-config .mcp.json \
  --allowedTools "mcp__tailorlock,Read,Agent" --output-format json
```

### Standalone API path (no Claude Code)

```bash
export ANTHROPIC_API_KEY=...
uv run tailorlock tailor jobs/nordavo-agentic-ai-engineer.md --provider anthropic --model claude-opus-5-5 --diff
```

`llm.py` uses `client.beta.messages.parse` with the `Patch` model as `output_format`, so the
shape is guaranteed and only the content is judged. The system prompt, master and policy are
one cached prefix; only the JD and the validator feedback vary per call. Server-side refusal
fallback is on by default (`--no-fallbacks` to turn it off).

## The policy

`data/policy.yaml` is the contract. Everything not listed under `editable` is locked.

```yaml
page_limit: 1
editable:
  title:   {max_chars: 60}
  summary: {min_chars: 150, max_chars: 400}
  skills:  {min_count: 8, max_count: 16}          # subset + order only; no new skills
  bullets: {rewrite: true, max_chars: 210, min_per_role: 2, max_per_role: 4,
            min_per_project: 1, max_per_project: 2, max_projects: 2}
rules:
  no_new_numbers: true
  forbidden_phrases: [results-driven, passionate, synergy, ...]
  forbidden_starters: [Responsible, Worked on, Helped, Was, I]
  no_first_person: true
```

## MCP tools

| Tool | What it does |
|---|---|
| `get_job(job)` / `list_jobs()` | read a JD by slug or project-relative path |
| `get_master()` | the master with ids |
| `get_policy()` | policy + the JSON schema a patch must satisfy |
| `baseline_patch_for(job)` | deterministic keyword-ranked starting patch |
| `validate_only(patch)` | cheap check while drafting |
| `render_patch(patch, job, note, attempt)` | validate -> apply -> render -> page check -> log. Returns `ok`, `errors`, `pages`, `diff_text`, `pdf_path`, `keyword_coverage`, `run_id` |
| `list_runs(limit, job)` | audit log |

## Evals

```bash
uv run python evals/run_evals.py --provider baseline
uv run python evals/run_evals.py --provider anthropic --model claude-opus-5-5
```

Per JD: did the first patch validate, how many rounds, pages, share of the JD's top-30
keywords present in the result, tokens and cost. The baseline is free and deterministic;
it is the floor a model has to beat. Results land in `evals/results/<provider>-<model>/`.

Baseline on the four bundled JDs: 4/4 pass, 4/4 first try, average coverage 0.43, $0. Two of the
four miss their coverage floor; that gap is what the LLM run has to close by rewriting.

### Real runs through Claude Code

Two headless `/tailor` runs on the owner's real data (2026-11-09):

| JD | turns | wall time | render attempts | cost |
|---|---|---|---|---|
| Nordavo, Agentic AI Engineer | 18 | 278 s | 2 | $1.83 |
| Uplers, Java/Spring Boot Backend | 17 | 360 s | 4 (two overflowed to page 2, then fit) | $2.32 |

Both produced one-page resumes in the owner's layout with every number unchanged. Full
tables and what the runs demonstrate: [evals/RESULTS.md](evals/RESULTS.md). Cost for the
Claude Code path comes from `--output-format json`; the MCP server cannot see the agent's
tokens, so the audit DB shows $0 for those runs.

## Things that went wrong while building this, and the fix

- **The Bash guard let writes through.** The locked-path regex anchored on `^` or `/`, which is
  right for a `file_path` argument and wrong for a path inside a shell command (`echo x >
  template/resume.typ`). Fix: anchor on any non-path character. Lesson: test hooks with the
  real JSON payloads, not by reading them.
- **The sample master would not load.** A YAML flow mapping with a value like `AWS (ECS, Lambda, S3)`
  splits on the commas. Pydantic's `extra="forbid"` caught it as two bogus keys. Quote such values.
- **mcp 2.x renamed FastMCP.** `from mcp.server.mcpserver import MCPServer`; same decorator API.
- **Forcing a tool call is a 400 on current models**, so the patch comes back through structured
  outputs (`output_format=Patch`) rather than a forced `tool_choice`.
- **A Typst function parameter named `right` shadowed the alignment constant**, so
  `align(right, right)` failed with "unexpected argument". Renamed the parameters.
- **The agent claimed it had put a project first when it had not.** Projects rendered in master
  order regardless of the patch. Now the order the patch lists projects is the order they render,
  so the agent's intent and the output agree.
- **The first two patches for the Java/Spring JD overflowed to two pages.** Not a bug: the
  renderer rejected them, fed back `page_overflow`, and the third patch fit. That loop is the
  point of the project.

## Security notes

- The agent has no write tool that reaches the locked layer; the hook is defence in depth.
- Secrets: the API key is read from the environment by the SDK; nothing is written to the repo.
- Failure halfway: every attempt renders to its own file and is logged before the next starts;
  the final PDF is only renamed into place on success.
- Cost: cache the stable prefix, cap attempts at 3, keep the subagents on cheaper models.

## Data files

- `data/master.yaml` is the owner's real resume and is **gitignored**. It was built from the
  confirmed facts in `job-search-assistant/me/master_resume.md`; every number on it is one the
  owner has signed off on.
- `data/master.example.yaml` is a fictional persona with the same structure. The tests run
  against it, and every command falls back to it when `data/master.yaml` is absent, so a fresh
  clone works without any private data.
- Id scheme: `sk-<name>` for skills, `exp-<company>-<role>` for roles with bullets
  `exp-<company>-<role>-<slug>`, `prj-<name>` for projects. Ids are stable; the agent addresses
  everything by id.

## Layout notes

The template reproduces the owner's existing LaTeX resume: Computer Modern, small-caps name,
steel-blue section titles over a rule, en-dash bullets with a bold lead-in label
("Payments & Reconciliation:"), bold key numbers, and grouped skills lines. Three things in the
data model exist only to serve that layout:

- `label` on a bullet is the bold lead-in. The agent may reword it (`relabel`) but cannot add
  one to a bullet that has none.
- `**double asterisks**` in bullet or summary text render bold. The renderer escapes every other
  Typst control character first, so the agent's text can never run as template code
  (`tests/test_pipeline.py::test_injection_in_bullet_does_not_execute`).
- `title.max_chars: 0` in the policy disables the title line, which this layout does not have.

The full master intentionally overflows to two pages (every bullet, three roles, two projects);
the agent's job is to pick the subset that fits one.
