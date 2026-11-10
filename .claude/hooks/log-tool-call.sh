#!/usr/bin/env bash
# PostToolUse hook: append a one-line audit record for every tailorlock MCP call.
set -euo pipefail
input="$(cat)"
mkdir -p "$CLAUDE_PROJECT_DIR/out"
printf '%s' "$input" | python3 -c '
import json, sys, time
d = json.load(sys.stdin)
name = d.get("tool_name", "")
inp = d.get("tool_input", {})
resp = d.get("tool_response", "")
# keep the log small: tool name, arg keys, response size
rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": name, "args": sorted(inp.keys()) if isinstance(inp, dict) else str(type(inp)),
       "resp_chars": len(json.dumps(resp)) if not isinstance(resp, str) else len(resp)}
print(json.dumps(rec))
' >> "$CLAUDE_PROJECT_DIR/out/tool-calls.jsonl"
exit 0
