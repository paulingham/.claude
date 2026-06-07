"""bash-write-guard.sh enforcement blind-spot closures (three holes).

Background: this session bypassed bash-write-guard.sh through three holes:

  Hole 1 — cp/mv not detected: `cp "$WT/$f" "$f"` copied protected files
    from a worktree into the main tree unblocked.
  Hole 2 — write_text()/write_bytes() not matched: matches_python_open_write
    keys on the literal `open(`, so `Path(...).write_text(t)` was invisible.
  Hole 3 — all .md treated as orchestrator-writable: .md at repo root /
    templates/ slipped through. Only .md under .claude/, memory/, rules/,
    pipeline-state/, and .claude/worktrees/ should be allowed.

These tests pin the new detectors. Run from /tmp so is_caller_in_worktree
returns false — this exercises the protected-path detectors + allowlist.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "bash-write-guard.sh"


def _run(command):
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


class Hole1CpMvDetection(unittest.TestCase):
    """cp/mv whose destination carries a protected extension and is not
    under /tmp or inside a worktree must block."""

    def test_cp_to_root_json_blocks(self):
        r = _run("cp /worktree/settings.json settings.json")
        self.assertEqual(r.returncode, 2,
                         f"cp to root .json must block; stderr={r.stderr}")

    def test_mv_to_root_sh_blocks(self):
        r = _run("mv build/foo.sh hooks/foo.sh")
        self.assertEqual(r.returncode, 2,
                         f"mv to root .sh must block; stderr={r.stderr}")

    def test_cp_to_root_yaml_blocks(self):
        r = _run("cp src/ci.yaml .github/ci.yaml")
        self.assertEqual(r.returncode, 2,
                         f"cp to root .yaml must block; stderr={r.stderr}")

    def test_cp_with_flags_blocks(self):
        r = _run("cp -f /src/settings.json ./settings.json")
        self.assertEqual(r.returncode, 2,
                         f"cp -f to root .json must block; stderr={r.stderr}")

    def test_cp_to_tmp_json_allowed(self):
        r = _run("cp settings.json /tmp/x.json")
        self.assertEqual(r.returncode, 0,
                         f"cp to /tmp must pass; stderr={r.stderr}")

    def test_cp_into_worktree_allowed(self):
        r = _run("cp src/settings.json "
                 "/repo/.claude/worktrees/agent-abc/settings.json")
        self.assertEqual(r.returncode, 0,
                         f"cp into worktree must pass; stderr={r.stderr}")

    def test_cp_no_protected_ext_allowed(self):
        r = _run("cp src/foo.txt dest/foo.txt")
        self.assertEqual(r.returncode, 0,
                         f"cp of unprotected ext must pass; stderr={r.stderr}")


class Hole2WriteTextWriteBytes(unittest.TestCase):
    """Path(...).write_text()/write_bytes() paired with a protected-extension
    path must block; learning jsonl + evidence writes still pass first."""

    def test_write_text_to_root_sh_blocks(self):
        r = _run("python3 -c \"from pathlib import Path; "
                 "Path('hooks/foo.sh').write_text('x')\"")
        self.assertEqual(r.returncode, 2,
                         f"write_text to .sh must block; stderr={r.stderr}")

    def test_write_text_to_root_json_blocks(self):
        r = _run("python3 -c \"from pathlib import Path; "
                 "Path('settings.json').write_text('{}')\"")
        self.assertEqual(r.returncode, 2,
                         f"write_text to .json must block; stderr={r.stderr}")

    def test_write_bytes_to_root_yaml_blocks(self):
        r = _run("python3 -c \"from pathlib import Path; "
                 "Path('ci.yaml').write_bytes(b'x')\"")
        self.assertEqual(r.returncode, 2,
                         f"write_bytes to .yaml must block; stderr={r.stderr}")

    def test_write_text_to_learning_jsonl_allowed(self):
        path = "/abs/learning/observations/x.jsonl"
        r = _run(f"python3 -c \"from pathlib import Path; "
                 f"Path('{path}').write_text('line')\"")
        self.assertEqual(r.returncode, 0,
                         f"write to learning jsonl must pass; stderr={r.stderr}")

    def test_write_text_to_unprotected_ext_allowed(self):
        r = _run("python3 -c \"from pathlib import Path; "
                 "Path('notes.txt').write_text('x')\"")
        self.assertEqual(r.returncode, 0,
                         f"write_text to .txt must pass; stderr={r.stderr}")

    def test_write_text_to_evidence_json_allowed(self):
        ev = "/abs/pipeline-state/task/verification-evidence.json"
        r = _run(f"python3 -c \"from pathlib import Path; "
                 f"Path('{ev}').write_text('{{}}')\"")
        self.assertEqual(r.returncode, 0,
                         f"write_text to evidence json must pass; stderr={r.stderr}")


class Hole3MdRootBlockedScopedAllowed(unittest.TestCase):
    """.md at repo root / templates/ blocks; .md under allowed roots passes."""

    def test_md_at_repo_root_blocks(self):
        r = _run("echo content > ROLLOUT.md")
        self.assertEqual(r.returncode, 2,
                         f"redirect to root .md must block; stderr={r.stderr}")

    def test_md_under_templates_blocks(self):
        r = _run("cp src/x.md templates/x.md")
        self.assertEqual(r.returncode, 2,
                         f"cp to templates .md must block; stderr={r.stderr}")

    def test_md_under_dotclaude_allowed(self):
        r = _run("echo content > /repo/.claude/notes.md")
        self.assertEqual(r.returncode, 0,
                         f".md under .claude/ must pass; stderr={r.stderr}")

    def test_md_under_memory_allowed(self):
        r = _run("echo content > /repo/memory/MEMORY.md")
        self.assertEqual(r.returncode, 0,
                         f".md under memory/ must pass; stderr={r.stderr}")

    def test_md_under_rules_allowed(self):
        r = _run("echo content > /repo/rules/core.md")
        self.assertEqual(r.returncode, 0,
                         f".md under rules/ must pass; stderr={r.stderr}")

    def test_md_under_pipeline_state_allowed(self):
        r = _run("echo content > /repo/pipeline-state/task/plan.md")
        self.assertEqual(r.returncode, 0,
                         f".md under pipeline-state/ must pass; stderr={r.stderr}")

    def test_md_inside_worktree_allowed(self):
        r = _run("echo content > "
                 "/repo/.claude/worktrees/agent-abc/ROLLOUT.md")
        self.assertEqual(r.returncode, 0,
                         f".md inside worktree must pass; stderr={r.stderr}")


if __name__ == "__main__":
    unittest.main()
