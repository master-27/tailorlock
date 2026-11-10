#!/usr/bin/env bash
# PreToolUse hook: block any attempt to modify the locked layer.
#
# Locked: template/**, data/policy.yaml, this hooks directory, .claude/settings.json.
# The agent tailors by producing a PATCH through the MCP server; it must never
# reach for the template or the rules. Exit 2 = block, stderr goes to the model.
set -euo pipefail
input="$(cat)"
tool="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')"

# A locked path may appear at the start of a string, after a slash, or after any
# shell separator (space, quote, '='), so do not anchor on ^ or / alone.
LOCKED_RE='(^|[^A-Za-z0-9_.-])(template/|data/policy\.yaml|\.claude/hooks/|\.claude/settings\.json)'

if [[ "$tool" == "Bash" ]]; then
  cmd="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"
  # only care about commands that can write
  if printf '%s' "$cmd" | grep -Eq '(>|>>|(^|[^A-Za-z])sed .*-i|(^|[^A-Za-z])(tee|mv|rm|cp|truncate|chmod|python3? -c|perl -[pi]) )' \
     && printf '%s' "$cmd" | grep -Eq "$LOCKED_RE"; then
    echo "BLOCKED by tailorlock guard: this Bash command writes to a locked path (template/, data/policy.yaml, .claude/hooks). Tailor by proposing a patch via the tailorlock MCP tools instead." >&2
    exit 2
  fi
  exit 0
fi

# Only writing tools are subject to the path check; reading the template is fine.
case "$tool" in
  Edit|Write|MultiEdit|NotebookEdit) ;;
  *) exit 0 ;;
esac

path="$(printf '%s' "$input" | python3 -c 'import json,sys; t=json.load(sys.stdin).get("tool_input",{}); print(t.get("file_path") or t.get("notebook_path") or "")')"
if printf '%s' "$path" | grep -Eq "$LOCKED_RE"; then
  echo "BLOCKED by tailorlock guard: '$path' is part of the locked layer. The layout and the rules belong to the resume owner. Use the tailorlock MCP tools (propose_patch / render_patch) to change content within policy." >&2
  exit 2
fi
exit 0
