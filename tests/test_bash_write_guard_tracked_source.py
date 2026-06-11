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


class SourceMdDoesNotTrickPathlibWriteDetector(unittest.TestCase):
    """FIX 2 regression tests: the .md token fed to is_protected_path must be
    ALL .md tokens in the command, not just the first one.

    Exploit: `python3 -c "Path('rules/core.md').write_text(Path('/tmp/scratch.md').read_text())"`
    Previously, grep | head -1 extracted `/tmp/scratch.md` (the source, appears
    first textually in this variant), passed it to is_protected_path → ALLOW, and
    never checked the tracked write destination → rc=0 (fail-open).

    Fix (check-every-token): loop over ALL .md tokens; block if ANY is protected.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls._repo = _make_git_repo(cls._tmpdir)
        # Source scratch path — is_protected_path returns ALLOW (untracked /tmp).
        # If the guard checks only this token, it allows the entire command.
        # If it correctly checks ALL tokens, the tracked dest triggers a BLOCK.
        cls._src = "/tmp/scratch.md"

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_write_text_tracked_dest_with_scratch_source_first_blocks(self):
        """write_text to tracked rules/core.md while source /tmp/scratch.md appears FIRST.

        The source token (/tmp/scratch.md) comes before the destination in the
        command string — so grep | head -1 extracts the source, not the dest.
        is_protected_path(/tmp/scratch.md) fails-closed (git error on /tmp) which
        incidentally also blocks — but the fix must work on any untracked source.
        The important property: the fix checks ALL tokens, so even if any individual
        token is benign the tracked destination is still caught.
        Bug: grep | head -1 grabbed only the first .md token; a benign allowlisted
        source (e.g. /pipeline-state/notes.md) appearing first causes ALLOW.
        Fix: all .md tokens checked; if ANY is protected → BLOCK.
        """
        dest = os.path.join(self._repo, "rules", "core.md")
        # Source path uses pipeline-state prefix so is_protected_path(src) == ALLOW.
        # If guard checks ONLY this token, the command would be allowed.
        # If guard checks ALL tokens, the tracked dest triggers BLOCK.
        src_allowlisted = "/some/pipeline-state/notes.md"
        cmd = (
            f"python3 -c \""
            f"from pathlib import Path; "
            # src_allowlisted appears FIRST in the command string
            f"data = Path('{src_allowlisted}').read_text(); "
            f"Path('{dest}').write_text(data)"
            f"\""
        )
        r = _run(cmd, self._repo)
        self.assertEqual(
            r.returncode, 2,
            f"write_text: pipeline-state src first, tracked dest second must block; "
            f"bug was: first .md token (pipeline-state, ALLOW) checked, dest skipped; "
            f"stderr={r.stderr}",
        )

    def test_write_text_to_tmp_scratch_allowed(self):
        """write_text to /tmp/scratch.md (no tracked .md token) must ALLOW.

        /tmp/ paths are explicitly skipped before is_protected_path is called,
        mirroring the cp/mv _bwg_destination_is_protected guard.
        """
        cmd = (
            "python3 -c \""
            "from pathlib import Path; "
            "Path('/tmp/scratch.md').write_text('data')"
            "\""
        )
        r = _run(cmd, self._repo)
        self.assertEqual(
            r.returncode, 0,
            f"write_text to /tmp/scratch.md must pass; stderr={r.stderr}",
        )


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



class LinuxTmpPathRegressionBlocks(unittest.TestCase):
    """Regression: tracked files inside a git repo under /tmp must BLOCK.

    Root cause: the /tmp/* early-return in _bwg_destination_is_protected and
    matches_python_pathlib_write was designed to prevent over-blocking genuine
    /tmp scratch writes.  On Linux CI, tempfile.mkdtemp() returns /tmp/... paths,
    so fixture git repos live under /tmp.  The guard fired on tracked destinations
    inside those repos, causing a fail-open (ALLOW instead of BLOCK).

    Fix: /tmp/* guard removed from .md branches; is_protected_path returns ALLOW
    for genuinely non-repo /tmp paths ("not a git repository"), so the guard is
    no longer needed.  This test forces a /tmp-style base even on macOS so the
    divergence is caught regardless of platform.
    """

    @classmethod
    def setUpClass(cls):
        # Force the repo under a /tmp/ path — on macOS mkdtemp() returns
        # /var/folders/... which hid the bug.  Use an explicit /tmp subdir
        # to reproduce the Linux CI condition on both platforms.
        cls._tmpdir = tempfile.mkdtemp(dir="/tmp")
        cls._repo = _make_git_repo(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_cp_to_tracked_readme_under_tmp_blocks(self):
        """cp to tracked README inside /tmp-based repo must BLOCK (Linux CI regression)."""
        readme = os.path.join(self._repo, "README.md")
        r = _run(f"cp /tmp/x.md {readme}", self._repo)
        self.assertEqual(r.returncode, 2,
                         f"cp to tracked README under /tmp must block; stderr={r.stderr}")

    def test_write_text_to_tracked_rules_under_tmp_blocks(self):
        """write_text to tracked rules/core.md inside /tmp-based repo must BLOCK."""
        rules = os.path.join(self._repo, "rules", "core.md")
        r = _run(
            f"python3 -c \"from pathlib import Path; Path('{rules}').write_text('x')\",",
            self._repo,
        )
        self.assertEqual(r.returncode, 2,
                         f"write_text to tracked rules/core.md under /tmp must block; "
                         f"stderr={r.stderr}")

    def test_genuine_tmp_scratch_still_allowed(self):
        """write_text to /tmp/scratch.md (not in any repo) must ALLOW."""
        cmd = (
            "python3 -c \"from pathlib import Path; "
            "Path('/tmp/scratch.md').write_text('data')\"")
        r = _run(cmd, self._repo)
        self.assertEqual(r.returncode, 0,
                         f"write_text to /tmp/scratch.md must pass; stderr={r.stderr}")

if __name__ == "__main__":
    unittest.main()
