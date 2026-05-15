"""Slice C2 + C3: bash-write-guard.sh must allow Bash writes to
`pipeline-state/*/verification-evidence.json` (regular + workstream layouts)
while preserving the existing settings.json protection (C3 regression guard).

Background: mirrors the `is_learning_jsonl_append` bypass at line 53-64.
The orchestrator may need to refresh a stale evidence stub in-cycle per
Iron Law 6; without this allowance, every shape (python open(...,'w'),
json.dump, > redirect) is blocked by the existing detectors.

ACs:
- C2: `python open(... 'w')` to evidence path → exit 0
- C2: `json.dump(...)` to evidence path → exit 0
- C2: `printf > path` redirect to evidence path → exit 0
  (note: the redirect detector at line 88-93 only targets settings.json +
  .sh today; the bare `printf > foo.json` shape is not caught — this test
  is a regression-anchor documenting the existing un-caught behaviour, NOT
  testing the new bypass. Future redirect-detector tightening must keep
  this shape allowed for verification-evidence.json paths.)
- C2: workstream-layout evidence path also matches
- C3: other .json writes (settings.json) still blocked
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "bash-write-guard.sh"


def _run(command):
    """Invoke from /tmp so is_caller_in_worktree returns false — this
    exercises the protected-path detectors + allowlist exclusively."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc_env = {**os.environ, "PWD": "/tmp"}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=proc_env,
        cwd="/tmp",
    )


EVIDENCE = "/abs/path/pipeline-state/some-task/verification-evidence.json"
WS_EVIDENCE = (
    "/abs/path/pipeline-state/workstreams/ws-x/some-task/"
    "verification-evidence.json"
)


class BashWriteGuardAllowsEvidenceJsonWrites(unittest.TestCase):
    """C2: every write shape the orchestrator might use to refresh a stale
    evidence stub must be allowed for pipeline-state/*/verification-evidence.json."""

    def test_python_open_write_evidence_allowed(self):
        r = _run(f"python3 -c \"open('{EVIDENCE}', 'w').write('{{}}')\"")
        self.assertEqual(
            r.returncode, 0,
            f"python open(..., 'w') to evidence path must pass; "
            f"stderr={r.stderr}",
        )

    def test_json_dump_to_evidence_allowed(self):
        r = _run(
            f"python3 -c \"import json; json.dump({{}}, open('{EVIDENCE}','w'))\""
        )
        self.assertEqual(
            r.returncode, 0,
            f"json.dump to evidence path must pass; stderr={r.stderr}",
        )

    def test_redirect_to_evidence_allowed(self):
        """Regression-anchor: today the redirect detector only targets
        settings.json + .sh files; bare `printf > foo.json` is not caught.
        This test documents that intent — future tightening of the redirect
        detector must add an evidence-json carve-out."""
        r = _run(f"printf '{{}}' > {EVIDENCE}")
        self.assertEqual(
            r.returncode, 0,
            f"redirect to evidence path must pass; stderr={r.stderr}",
        )

    def test_workstream_evidence_python_open_allowed(self):
        r = _run(f"python3 -c \"open('{WS_EVIDENCE}', 'w').write('{{}}')\"")
        self.assertEqual(
            r.returncode, 0,
            f"workstream evidence python open must pass; stderr={r.stderr}",
        )

    def test_workstream_evidence_json_dump_allowed(self):
        r = _run(
            f"python3 -c \"import json; json.dump({{}}, open('{WS_EVIDENCE}','w'))\""
        )
        self.assertEqual(
            r.returncode, 0,
            f"workstream json.dump must pass; stderr={r.stderr}",
        )


class BashWriteGuardStillBlocksSettingsJson(unittest.TestCase):
    """C3 regression guard: the evidence-json bypass MUST NOT widen to
    settings.json — every prior settings.json protection holds."""

    def test_settings_json_python_open_w_still_blocks(self):
        r = _run("python3 -c \"open('settings.json', 'w')\"")
        self.assertEqual(
            r.returncode, 2,
            f"settings.json open('w') must still block; stderr={r.stderr}",
        )

    def test_settings_json_json_dump_still_blocks(self):
        r = _run(
            "python3 -c \"import json; json.dump({}, open('settings.json','w'))\""
        )
        self.assertEqual(
            r.returncode, 2,
            f"settings.json json.dump must still block; stderr={r.stderr}",
        )

    def test_other_pipeline_state_json_still_blocks(self):
        """Defensive: only verification-evidence.json gets the bypass,
        not arbitrary .json under pipeline-state/."""
        other = "/abs/path/pipeline-state/some-task/random.json"
        r = _run(f"python3 -c \"open('{other}', 'w')\"")
        self.assertEqual(
            r.returncode, 2,
            f"other pipeline-state json must still block; stderr={r.stderr}",
        )

    def test_evidence_json_bak_suffix_blocked(self):
        """Regex anchor regression guard: verification-evidence.json.bak must
        NOT match the allowlist (mirrors orchestrator-discipline.sh suite).
        The asymmetry between the two hooks would otherwise let .bak through
        bash-write-guard while orchestrator-discipline blocks it."""
        bak = "/abs/path/pipeline-state/some-task/verification-evidence.json.bak"
        r = _run(f"python3 -c \"open('{bak}', 'w')\"")
        self.assertEqual(
            r.returncode, 2,
            f"evidence .json.bak must still block; stderr={r.stderr}",
        )

    def test_evidence_json_tmp_suffix_blocked(self):
        """Regex anchor regression guard: verification-evidence.json.tmp must
        NOT match the allowlist."""
        tmp = "/abs/path/pipeline-state/some-task/verification-evidence.json.tmp"
        r = _run(f"python3 -c \"open('{tmp}', 'w')\"")
        self.assertEqual(
            r.returncode, 2,
            f"evidence .json.tmp must still block; stderr={r.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
