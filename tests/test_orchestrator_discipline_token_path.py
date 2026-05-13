"""Gap 1 — orchestrator-discipline must allow pipeline-state .token writes.

Background: the orchestrator writes approval tokens to
`pipeline-state/{task-id}/approval.token` (regular layout) and
`pipeline-state/workstreams/{ws}/{task-id}/approval.token` (workstream
layout). These are orchestrator-state files, NOT source code — Iron Law 3
(orchestrator never writes source code) does not apply. Before this fix,
`is_path_allow_listed` rejected any file path not matching `.md`,
`.claude/automation/`, `.claude/hooks/`, `.claude/worktrees/`, or
`.claude-sessions/`, forcing a python3-inline-write workaround for every
approval token. This test pins the new allowance.

Test approach: invoke the hook with a JSON payload mimicking PreToolUse
Write input. The hook's `is_path_allow_listed` is internal; we exercise
the visible behaviour (exit 0 = allowed, exit 2 = blocked) via the hook
entry point.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "orchestrator-discipline.sh"


def _run_hook(file_path: str, subagent_type: str = "") -> subprocess.CompletedProcess:
    """Invoke the hook with a synthetic PreToolUse Write payload.

    Critical: run cwd from a temporary directory OUTSIDE any worktree so the
    `is_caller_a_subagent` CWD fallback does not bypass the path allowlist
    check (the hook treats `.claude/worktrees/...` as implicit subagent
    context). We are exclusively testing `is_path_allow_listed` here.
    """
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "stub"},
        "subagent_type": subagent_type,
    }
    with tempfile.TemporaryDirectory() as scratch:
        return subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=scratch,
            env={
                "CLAUDE_HOOK_PROFILE": "minimal",
                "HOME": scratch,
                "PATH": os.environ.get(
                    "PATH", "/usr/local/bin:/usr/bin:/bin"),
                "CLAUDE_CONFIG_DIR": str(ROOT),
            },
        )


class OrchestratorDisciplineAllowsTokenPaths(unittest.TestCase):
    def test_pipeline_state_approval_token_allowed(self):
        """Regular-layout approval token must be writable by orchestrator."""
        result = _run_hook("/abs/path/pipeline-state/foo/approval.token")
        self.assertEqual(result.returncode, 0,
                         msg=f"expected allow (exit 0), got {result.returncode}; "
                             f"stderr={result.stderr}")

    def test_workstream_approval_token_allowed(self):
        """Workstream-layout approval token must be writable by orchestrator."""
        result = _run_hook(
            "/abs/path/pipeline-state/workstreams/bar/baz/approval.token")
        self.assertEqual(result.returncode, 0,
                         msg=f"expected allow (exit 0), got {result.returncode}; "
                             f"stderr={result.stderr}")

    def test_pipeline_state_arbitrary_token_allowed(self):
        """Defensive: any .token under pipeline-state is orchestrator state."""
        result = _run_hook("/abs/path/pipeline-state/foo/state.token")
        self.assertEqual(result.returncode, 0,
                         msg=f"expected allow (exit 0), got {result.returncode}; "
                             f"stderr={result.stderr}")

    def test_pipeline_state_source_file_still_blocked(self):
        """Regression guard: only .token gains the allowance, not .py/.sh/etc."""
        result = _run_hook("/abs/path/pipeline-state/foo/source.py")
        self.assertEqual(result.returncode, 2,
                         msg=f"expected block (exit 2), got {result.returncode}; "
                             f"stderr={result.stderr}")


if __name__ == "__main__":
    unittest.main()
