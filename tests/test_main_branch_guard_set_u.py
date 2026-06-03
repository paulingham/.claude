"""SEC-2 regression: main-branch-guard.sh must BLOCK (exit 2) `git branch -d main`
even when CLAUDE_WORKTREE_PATH is unset and the hook runs under `set -uo pipefail`.

Before the fix: line 75 referenced $CLAUDE_WORKTREE_PATH without `:-`, so bash
crashed (exit 127/1) under set -uo pipefail when the var was unset.
Claude Code treats non-2 exit as NON-blocking, silently allowing branch deletion.

After the fix: `${CLAUDE_WORKTREE_PATH:-}` is used, so the crash is avoided and
the hook correctly reaches the `is_forbidden_command` check → exits 2 (BLOCKED).

Test strategy: invoke `hooks/main-branch-guard.sh` via `env -u CLAUDE_WORKTREE_PATH
bash hooks/main-branch-guard.sh` from a real git repo (main branch), asserting
exit 2. The RED state (before fix) exits 127 or 0; the GREEN state (after fix)
exits 2.
"""
import json
import os
import subprocess
import tempfile
import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "main-branch-guard.sh"


def _make_git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo on 'main' branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                   check=True, env=env, capture_output=True)
    (repo / "README").write_text("init\n")
    subprocess.run(["git", "-C", str(repo), "add", "README"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"],
                   check=True, env=env, capture_output=True)
    return repo


class MainBranchGuardSetU(unittest.TestCase):
    """SEC-2: hook must exit 2 (BLOCKED) even when CLAUDE_WORKTREE_PATH is unset."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".claude").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_hook_without_worktree_path(self, command: str, cwd: Path):
        """Run hook under env -u CLAUDE_WORKTREE_PATH bash <hook>."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        # Build env without CLAUDE_WORKTREE_PATH.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_WORKTREE_PATH"}
        env["HOME"] = str(self.tmp)
        env["CLAUDE_HOOK_PROFILE"] = "minimal"
        env["CLAUDE_SESSION_ID"] = f"sec2-test-{os.getpid()}"
        # Use env -u to guarantee the var is unset regardless of inherited env.
        return subprocess.run(
            ["env", "-u", "CLAUDE_WORKTREE_PATH", "bash", str(HOOK)],
            input=payload, capture_output=True, text=True, cwd=str(cwd),
            timeout=15, env=env,
        )

    def test_branch_delete_main_blocked_when_worktree_path_unset(self):
        """git branch -d main with CLAUDE_WORKTREE_PATH unset must exit 2 (BLOCKED).

        Before fix: hook crashes with exit 127 under set -uo pipefail.
        After fix: hook reaches is_forbidden_command check → exit 2.
        """
        repo = _make_git_repo(self.tmp)
        result = self._run_hook_without_worktree_path("git branch -d main", repo)
        self.assertEqual(
            result.returncode, 2,
            f"expected exit 2 (BLOCKED) but got {result.returncode}; "
            f"stderr={result.stderr!r}. "
            f"If exit is 127/1, the set-u crash-passthrough is present (pre-fix).",
        )

    def test_safe_command_allowed_when_worktree_path_unset(self):
        """git status (read-only) must exit 0 (allowed) even with CLAUDE_WORKTREE_PATH unset."""
        repo = _make_git_repo(self.tmp)
        result = self._run_hook_without_worktree_path("git status", repo)
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 (allowed) for read-only command; "
            f"stderr={result.stderr!r}",
        )

    def test_branch_delete_non_main_allowed_when_worktree_path_unset(self):
        """git branch -d old-feature (non-main, non-current) must exit 0 (allowed)."""
        repo = _make_git_repo(self.tmp)
        # Create the branch to delete so git can resolve it exists.
        env_git = {**os.environ,
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(repo), "branch", "old-feature"],
                       check=True, env=env_git, capture_output=True)
        result = self._run_hook_without_worktree_path(
            "git branch -d old-feature", repo
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 (allowed) for non-main branch delete; "
            f"stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
