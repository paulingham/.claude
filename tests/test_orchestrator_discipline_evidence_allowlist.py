"""Slice C1: orchestrator-discipline.sh must allow Write/Edit to
`pipeline-state/*/verification-evidence.json` (regular + workstream layouts).

Background: when the freshness gate's `pipeline-state/unknown/...` fallback
gets stuck with a stale stub, the orchestrator needs to be able to refresh
it in-cycle per Iron Law 6. The existing `.token` allowance at line 35 is
the precedent shape; this slice extends the same mechanism to the JSON
evidence file.

ACs:
- C1: regular-layout evidence path → exit 0
- C1: workstream-layout evidence path → exit 0
- C1 (regression guard): other JSON files under pipeline-state still blocked
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "orchestrator-discipline.sh"


def _run_hook(file_path: str) -> subprocess.CompletedProcess:
    """Invoke orchestrator-discipline.sh from /tmp so the worktree CWD
    fallback does not bypass the path allowlist check (we want to exercise
    is_path_allow_listed exclusively)."""
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "stub"},
        "subagent_type": "",
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


class OrchestratorDisciplineAllowsEvidenceJson(unittest.TestCase):
    def test_evidence_json_write_allowed(self):
        """Regular-layout verification-evidence.json must be writable."""
        r = _run_hook(
            "/abs/path/pipeline-state/some-task/verification-evidence.json")
        self.assertEqual(
            r.returncode, 0,
            msg=f"expected allow (exit 0), got {r.returncode}; "
                f"stderr={r.stderr}",
        )

    def test_workstream_evidence_json_write_allowed(self):
        """Workstream-layout verification-evidence.json must be writable."""
        r = _run_hook(
            "/abs/path/pipeline-state/workstreams/ws-x/some-task/"
            "verification-evidence.json")
        self.assertEqual(
            r.returncode, 0,
            msg=f"expected allow (exit 0), got {r.returncode}; "
                f"stderr={r.stderr}",
        )

    def test_other_pipeline_state_json_still_blocked(self):
        """Regression guard: only verification-evidence.json gets the
        allowance, not arbitrary .json under pipeline-state/."""
        r = _run_hook("/abs/path/pipeline-state/some-task/random.json")
        self.assertEqual(
            r.returncode, 2,
            msg=f"expected block (exit 2), got {r.returncode}; "
                f"stderr={r.stderr}",
        )

    def test_evidence_json_bak_suffix_blocked(self):
        """`$` anchor regression guard: verification-evidence.json.bak must
        NOT match (per H2 in plan risk table)."""
        r = _run_hook(
            "/abs/path/pipeline-state/some-task/verification-evidence.json.bak")
        self.assertEqual(
            r.returncode, 2,
            msg=f"expected block (exit 2) for .json.bak; got {r.returncode}; "
                f"stderr={r.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
