# Eval results

Two providers are measured against the same four job descriptions in `evals/jds/`:
the free deterministic baseline (keyword-overlap selection, no rewrites) and the full
Claude Code `/tailor` flow (JD-analyst subagent, draft, validate, render, critic, re-render).

Coverage = share of the JD's top-30 extracted keywords present in the rendered resume text.
It is a cheap proxy, not a quality score; the critic subagent and a human review carry quality.

## Baseline provider (no LLM), 2026-11-10

| JD | ok | first try | attempts | pages | coverage | cost |
|---|---|---|---|---|---|---|
| axionix-nodejs-backend | yes | yes | 1 | 1 | 0.50 | $0 |
| nordavo-agentic-ai-engineer | yes | yes | 1 | 1 | 0.40 | $0 |
| ruloans-fullstack-sde1 | yes | yes | 1 | 1 | 0.20 | $0 |
| uplers-java-springboot-backend | yes | yes | 1 | 1 | 0.63 | $0 |

4/4 pass, 4/4 valid first try, average coverage 0.43, 0.2 s per resume. Two JDs miss their
coverage floor in `expectations.json`; that gap is what the LLM has to close by rewriting.

Reproduce: `uv run python evals/run_evals.py --provider baseline`

## Claude Code `/tailor` runs, 2026-11-09

Headless invocation, main agent on the session's default model, `jd-analyst` on Haiku,
`resume-critic` on Sonnet. Cost from `--output-format json` (`total_cost_usd`).

| JD | turns | wall time | render attempts | result | coverage | cost |
|---|---|---|---|---|---|---|
| nordavo-agentic-ai-engineer | 18 | 278 s | 2 (both ok; 2nd after critic) | 1 page | 0.40 -> 0.67 | $1.83 |
| uplers-java-springboot-backend | 17 | 360 s | 4 (1st and 2nd overflowed to 2 pages, 3rd ok, 4th after critic) | 1 page | 0.63 -> 0.70 | $2.32 |

What the runs demonstrate:

- **The page-overflow feedback loop works on real input.** Uplers attempts 1 and 2 rendered to
  two pages; the renderer rejected both with `page_overflow`, the agent trimmed, attempt 3 fit.
- **The agent never touched a file.** All changes arrived as patches through `render_patch`;
  the PreToolUse guard hook was never triggered because the agent never tried.
- **Facts stayed put.** Every number on both resumes is the master's number. Where the JD asked
  for something the master lacks (Kubernetes, rate limiting), the agent reported the gap
  instead of inventing it.
- **The owner's framing rule held.** The Java/Spring JD got Java/Spring framing in the summary
  and Farmart bullets; the Node.js side project stayed Node.js.
- **The critic earned its cost.** It removed three unsupported claims from the Nordavo draft
  ("reviews every line", "daily", "unattended") and swapped one skill.

Known limit: the MCP server cannot see the agent's token usage, so the SQLite audit log shows
$0 for Claude Code runs. Cost comes from the CLI's JSON output. The standalone API provider
(`--provider anthropic`) logs exact tokens and USD per attempt.

Reproduce (needs Claude Code):

```bash
claude -p "/tailor jobs/nordavo-agentic-ai-engineer.md" --mcp-config .mcp.json \
  --allowedTools "mcp__tailorlock,Read,Agent" --output-format json
```
