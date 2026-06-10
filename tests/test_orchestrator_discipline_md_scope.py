"""orchestrator-discipline.sh — block-by-protected-location for .md paths.

Background: the old `is_path_allow_listed` used a `.claude/` substring check
that matched EVERY file in a repo whose root IS `.claude` (the harness repo).
This let the orchestrator write tracked source files (README.md, PORTING-NOTES.md,
etc.) directly to main.

Fix: replace the substring allow with `is_protected_path` from
`hooks/_lib/is-protected-path.sh`.  The helper consults the git index:
git-tracked files or net-new files in a tracked directory → BLOCK; genuine
untracked orchestrator-state paths → ALLOW.

This test builds a REAL `.claude`-named git repo (as a fixture) so that:
  - README.md and rules/core.md are committed → git-tracked → BLOCK
  - pipeline-state/task/plan.md is untracked AND in a dir with NO tracked
    siblings → ALLOW
  - agents/new-x.md is untracked but agents/ is tracked → BLOCK
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "orchestrator-discipline.sh"


def _make_git_repo(base: str) -> str:
    """Create a minimal .claude-named git repo inside base, return its path."""
    repo = os.path.join(base, "proj.claude")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "T"], check=True)
    # Commit README.md (tracked root doc)
    readme = os.path.join(repo, "README.md")
    Path(readme).write_text("# readme\n")
    subprocess.run(["git", "-C", repo, "add", "README.md"], check=True)
    # Commit rules/core.md
    os.makedirs(os.path.join(repo, "rules"))
    Path(os.path.join(repo, "rules", "core.md")).write_text("# core\n")
    subprocess.run(["git", "-C", repo, "add", "rules/core.md"], check=True)
    # Commit agents/ with a seed file so parent probe finds a sibling
    os.makedirs(os.path.join(repo, "agents"))
    Path(os.path.join(repo, "agents", "existing.md")).write_text("# agent\n")
    subprocess.run(["git", "-C", repo, "add", "agents/existing.md"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
    # Create untracked pipeline-state dir (no tracked siblings)
    ps_dir = os.path.join(repo, "pipeline-state", "task")
    os.makedirs(ps_dir)
    return repo


def _run_hook(file_path: str, repo: str) -> subprocess.CompletedProcess:
    """Run hook from a scratch dir; supply CLAUDE_CONFIG_DIR so libs resolve."""
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


class GitFixtureBlocksTrackedFiles(unittest.TestCase):
    """Tracked files in the .claude-named repo must be BLOCKED."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_tracked_readme_blocks(self):
        path = os.path.join(self._repo, "README.md")
        r = _run_hook(path, self._repo)
        self.assertEqual(r.returncode, 2,
                         f"tracked README must block; stderr={r.stderr}")

    def test_tracked_rules_core_md_blocks(self):
        path = os.path.join(self._repo, "rules", "core.md")
        r = _run_hook(path, self._repo)
        self.assertEqual(r.returncode, 2,
                         f"tracked rules/core.md must block; stderr={r.stderr}")

    def test_net_new_in_agents_tracked_dir_blocks(self):
        path = os.path.join(self._repo, "agents", "new-x.md")
        r = _run_hook(path, self._repo)
        self.assertEqual(r.returncode, 2,
                         f"net-new agents/new-x.md must block; stderr={r.stderr}")


class GitFixtureAllowsOrchestratorStatePaths(unittest.TestCase):
    """Genuine orchestrator-state paths must be ALLOWED."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_untracked_pipeline_state_plan_allowed(self):
        path = os.path.join(self._repo, "pipeline-state", "task", "plan.md")
        r = _run_hook(path, self._repo)
        self.assertEqual(r.returncode, 0,
                         f"untracked pipeline-state plan must pass; stderr={r.stderr}")

    def test_empty_path_allowed(self):
        r = _run_hook("", self._repo)
        self.assertEqual(r.returncode, 0,
                         f"empty path must pass; stderr={r.stderr}")


class WorktreePathAllowed(unittest.TestCase):
    """Paths inside .claude/worktrees/ must always be ALLOWED."""

    def _run(self, path: str) -> subprocess.CompletedProcess:
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": "stub"},
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

    def test_worktree_path_allowed(self):
        r = self._run("/some/.claude/worktrees/agent-abc/ROLLOUT.md")
        self.assertEqual(r.returncode, 0,
                         f".md inside worktree must pass; stderr={r.stderr}")


if __name__ == "__main__":
    unittest.main()
