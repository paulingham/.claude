"""bash-write-guard.sh — block-by-protected-location for .md paths.

Background: the old `is_protected_md` used a substring allow list
(`/\.claude/`, `/memory/`, `/rules/`, `/pipeline-state/`) that matched every
file in a repo whose root IS `.claude` (the harness repo itself).  Redirects
and write_text calls to tracked source files like README.md passed through.

Fix: the three .md detector branches (matches_protected_redirect,
matches_python_pathlib_write, _bwg_destination_is_protected) now call
`is_protected_path` from `hooks/_lib/is-protected-path.sh`.

This test builds a REAL `.claude`-named git repo (fixture) to exercise the
new git-index based decision:
  - redirect/write_text/cp → tracked README.md   → BLOCK (rc 2)
  - redirect/write_text/cp → tracked rules/core.md → BLOCK (rc 2)
  - redirect/write_text/cp → untracked pipeline-state plan.md → ALLOW (rc 0)
  - caller in worktree (CLAUDE_WORKTREE_PATH set)  → ALLOW (rc 0)
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "bash-write-guard.sh"


def _make_git_repo(base: str) -> str:
    """Create a minimal .claude-named git repo inside base, return its path."""
    repo = os.path.join(base, "proj.claude")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "T"], check=True)
    # Commit README.md
    Path(os.path.join(repo, "README.md")).write_text("# readme\n")
    subprocess.run(["git", "-C", repo, "add", "README.md"], check=True)
    # Commit rules/core.md
    os.makedirs(os.path.join(repo, "rules"))
    Path(os.path.join(repo, "rules", "core.md")).write_text("# core\n")
    subprocess.run(["git", "-C", repo, "add", "rules/core.md"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
    # Create untracked pipeline-state dir (no tracked siblings in that dir)
    ps_dir = os.path.join(repo, "pipeline-state", "task")
    os.makedirs(ps_dir)
    return repo


def _run(command: str, repo: str, worktree_path: str = "") -> subprocess.CompletedProcess:
    """Invoke from /tmp so is_caller_in_worktree returns false (unless
    CLAUDE_WORKTREE_PATH is set), exercising the protected-path detectors."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**os.environ, "PWD": "/tmp"}
    if worktree_path:
        env["CLAUDE_WORKTREE_PATH"] = worktree_path
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd="/tmp",
    )


class RedirectToTrackedMdBlocks(unittest.TestCase):
    """Redirect (>) to a git-tracked .md file must BLOCK."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_redirect_to_tracked_readme_blocks(self):
        readme = os.path.join(self._repo, "README.md")
        r = _run(f"echo content > {readme}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"redirect to tracked README must block; stderr={r.stderr}")

    def test_redirect_to_tracked_rules_core_blocks(self):
        rules = os.path.join(self._repo, "rules", "core.md")
        r = _run(f"echo content > {rules}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"redirect to tracked rules/core.md must block; stderr={r.stderr}")


class WriteTextToTrackedMdBlocks(unittest.TestCase):
    """write_text to a git-tracked .md file must BLOCK."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_write_text_to_tracked_rules_core_blocks(self):
        rules = os.path.join(self._repo, "rules", "core.md")
        r = _run(
            f"python3 -c \"from pathlib import Path; Path('{rules}').write_text('x')\"",
            self._repo,
        )
        self.assertEqual(r.returncode, 2,
                         f"write_text to tracked rules/core.md must block; stderr={r.stderr}")


class CpToTrackedMdBlocks(unittest.TestCase):
    """cp to a git-tracked .md file must BLOCK."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_cp_to_tracked_readme_blocks(self):
        readme = os.path.join(self._repo, "README.md")
        r = _run(f"cp /tmp/x.md {readme}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"cp to tracked README must block; stderr={r.stderr}")


class UntrackedPipelineStateAllowed(unittest.TestCase):
    """Writes to untracked pipeline-state paths must be ALLOWED."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_redirect_to_untracked_pipeline_state_allowed(self):
        plan = os.path.join(self._repo, "pipeline-state", "task", "plan.md")
        r = _run(f"echo content > {plan}", self._repo)
        self.assertEqual(r.returncode, 0,
                         f"redirect to untracked pipeline-state plan must pass; stderr={r.stderr}")


class WorktreeCallerAllowed(unittest.TestCase):
    """When CLAUDE_WORKTREE_PATH is set to a worktree path, all writes pass."""

    def test_worktree_env_bypasses_guard(self):
        r = _run(
            "echo x > /some/README.md",
            repo="",
            worktree_path="/home/user/.claude/worktrees/agent-abc",
        )
        self.assertEqual(r.returncode, 0,
                         f"worktree caller must pass; stderr={r.stderr}")


class SourceMdDoesNotTrickRedirectDetector(unittest.TestCase):
    """FIX 1 regression tests: the .md token fed to is_protected_path must be
    the redirect DESTINATION, not the first .md token in the command string.

    Exploit: `cat /some/pipeline-state/notes.md > <repo>/rules/core.md`
    Previously, grep extracted `/some/pipeline-state/notes.md` (the source)
    as the first .md token. is_protected_path allows it (pipeline-state allowlist)
    and returns 1 (ALLOW), so the tracked destination is never checked → rc=0.

    The src uses the pipeline-state allowlist path so is_protected_path(src)
    explicitly returns ALLOW — proving only the destination check matters.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)
        # Source is a pipeline-state path — is_protected_path returns ALLOW (rc=1)
        # via the explicit allowlist. If the guard checks this token, it allows
        # the entire command. If it correctly checks the DESTINATION, it blocks.
        cls._src = "/some/pipeline-state/notes.md"

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_cat_pipeline_state_src_redirect_to_tracked_core_blocks(self):
        """cat /some/pipeline-state/notes.md > <repo>/rules/core.md must BLOCK.

        Source is pipeline-state (ALLOW by allowlist). Destination is tracked.
        Bug: grep-first-token extracts the source (ALLOW) and skips the dest.
        Fix: extract only the token after the > operator.
        """
        dest = os.path.join(self._repo, "rules", "core.md")
        r = _run(f"cat {self._src} > {dest}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"cat pipeline-state-src.md > tracked/core.md must block; "
                         f"bug was: first .md token (src, allowlisted) was checked "
                         f"and allowed, destination never inspected; stderr={r.stderr}")

    def test_compound_redirect_second_target_tracked_blocks(self):
        """echo x > pipeline-state/a.md; echo y > <repo>/README.md — second must BLOCK.

        First redirect target (pipeline-state path) is allowlisted → ALLOW.
        Second redirect target (<repo>/README.md) IS tracked → must BLOCK.
        Bug: only the first .md token is checked; second write slips through.
        Fix: loop over ALL redirect-destination tokens, block if ANY is protected.
        """
        ps_dest = "/some/pipeline-state/scratch.md"
        readme = os.path.join(self._repo, "README.md")
        r = _run(f"echo x > {ps_dest}; echo y > {readme}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"compound cmd: second redirect to tracked README must block; "
                         f"bug was: only first .md token (pipeline-state, ALLOW) "
                         f"was checked; stderr={r.stderr}")


if __name__ == "__main__":
    unittest.main()
