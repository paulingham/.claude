"""orchestrator-discipline.sh — Hole 3: tighten the blanket .md allowance.

Background: `is_path_allow_listed` allowed EVERY `.md` path. The orchestrator
could write ROLLOUT.md / PORTING-NOTES.md / README.md at repo root and any
templates/*.md directly. Tighten so .md is allowed ONLY under .claude/,
memory/, rules/, or pipeline-state/. The existing worktree clause
(.claude/worktrees/) must keep .md inside a worktree ALLOWED.
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
    """Run from a scratch dir OUTSIDE any worktree so the CWD subagent
    fallback does not bypass is_path_allow_listed."""
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
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "CLAUDE_CONFIG_DIR": str(ROOT),
            },
        )


class MdAtRootOrTemplatesBlocked(unittest.TestCase):
    def test_rollout_md_at_root_blocks(self):
        r = _run_hook("/repo/ROLLOUT.md")
        self.assertEqual(r.returncode, 2,
                         f"root ROLLOUT.md must block; stderr={r.stderr}")

    def test_readme_md_at_root_blocks(self):
        r = _run_hook("/repo/README.md")
        self.assertEqual(r.returncode, 2,
                         f"root README.md must block; stderr={r.stderr}")

    def test_templates_md_blocks(self):
        r = _run_hook("/repo/templates/agent.md")
        self.assertEqual(r.returncode, 2,
                         f"templates/agent.md must block; stderr={r.stderr}")


class MdUnderAllowedRootsAllowed(unittest.TestCase):
    def test_md_under_dotclaude_allowed(self):
        r = _run_hook("/repo/.claude/notes.md")
        self.assertEqual(r.returncode, 0,
                         f".claude/notes.md must pass; stderr={r.stderr}")

    def test_md_under_memory_allowed(self):
        r = _run_hook("/repo/memory/MEMORY.md")
        self.assertEqual(r.returncode, 0,
                         f"memory/MEMORY.md must pass; stderr={r.stderr}")

    def test_md_under_rules_allowed(self):
        r = _run_hook("/repo/rules/core.md")
        self.assertEqual(r.returncode, 0,
                         f"rules/core.md must pass; stderr={r.stderr}")

    def test_md_under_pipeline_state_allowed(self):
        r = _run_hook("/repo/pipeline-state/task/plan.md")
        self.assertEqual(r.returncode, 0,
                         f"pipeline-state/.../plan.md must pass; stderr={r.stderr}")

    def test_md_inside_worktree_allowed(self):
        r = _run_hook("/repo/.claude/worktrees/agent-abc/ROLLOUT.md")
        self.assertEqual(r.returncode, 0,
                         f".md inside worktree must pass; stderr={r.stderr}")

    def test_empty_path_allowed(self):
        r = _run_hook("")
        self.assertEqual(r.returncode, 0,
                         f"empty path must pass; stderr={r.stderr}")


if __name__ == "__main__":
    unittest.main()
