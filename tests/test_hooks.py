"""The guard hook is part of the security boundary, so it gets tested with the
exact JSON payloads Claude Code sends to PreToolUse hooks."""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard-locked-files.sh"


def run_hook(tool_name: str, tool_input: dict) -> int:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
    return subprocess.run([str(HOOK)], input=payload, text=True, capture_output=True, env=env).returncode


@pytest.mark.parametrize("tool,inp", [
    ("Edit", {"file_path": "template/resume.typ"}),
    ("Write", {"file_path": str(ROOT / "template" / "resume.typ")}),
    ("Write", {"file_path": "data/policy.yaml"}),
    ("Edit", {"file_path": ".claude/hooks/guard-locked-files.sh"}),
    ("Edit", {"file_path": ".claude/settings.json"}),
    ("Bash", {"command": "echo x > template/resume.typ"}),
    ("Bash", {"command": 'sed -i "" s/1/2/ data/policy.yaml'}),
    ("Bash", {"command": "rm -f .claude/hooks/guard-locked-files.sh"}),
    ("Bash", {"command": "cp /tmp/x.typ /abs/template/resume.typ"}),
    ("Bash", {"command": "cat x | tee template/resume.typ"}),
])
def test_locked_paths_are_blocked(tool, inp):
    assert run_hook(tool, inp) == 2


@pytest.mark.parametrize("tool,inp", [
    ("Edit", {"file_path": "data/master.yaml"}),
    ("Write", {"file_path": "jobs/new-job.md"}),
    ("Bash", {"command": "cat template/resume.typ"}),
    ("Bash", {"command": "echo x >> data/master.yaml"}),
    ("Bash", {"command": "uv run tailorlock render"}),
    ("Bash", {"command": "ls -la template/"}),
    ("Read", {"file_path": "template/resume.typ"}),
])
def test_everything_else_is_allowed(tool, inp):
    assert run_hook(tool, inp) == 0
