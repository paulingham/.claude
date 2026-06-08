"""Test-suite-wide pytest conftest.

Side effect: prepend `${REPO_ROOT}/hooks/_lib` to `sys.path` so test files
can import sandbox-verify (and future) helpers without per-file
`sys.path.insert(...)` boilerplate. Pytest auto-loads any `conftest.py`
in the test root before collecting any test file in that directory.

History: Story 1 of the sandbox-verify epic spawned a fix-engineer to add
per-file `sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))` lines.
Story 2 (this file) makes that the conftest's responsibility instead, so
Story 3/4 authors do not need to remember the boilerplate.

Idempotency: the insert is gated on `not in sys.path` so re-loads (e.g.
pytest's `--collect-only` followed by a normal run) do not duplicate
entries.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_HOOKS_LIB = str(Path(__file__).resolve().parent.parent / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


# --- Suite-wide speed guard ------------------------------------------------
# Several tests invoke real hook scripts via subprocess. `hooks/quality-gate.sh`
# runs the project's OWN pytest suite TWICE (_qg_check_tests_python →
# _qg_pytest_runs) whenever it is triggered on a `gh pr create` command. Without
# the guard below, a single quality-gate hook test recursively re-runs the whole
# suite, turning a seconds-long run into a ~10-minute one. We export a
# process-wide default at import time (before any test runs) so the many
# `{**os.environ, ...}` env copies the tests build for subprocess.run inherit it.
# Tests that genuinely exercise the heavy path can pop the var from their env.
os.environ.setdefault("CLAUDE_QG_SKIP_CHECKS", "1")


@pytest.fixture
def make_git_worktree(tmp_path):
    """Create a tmp git repo with one commit; HEAD is controllable.

    Used by tests/test_freshness_guard.py to author worktrees with known
    git_head values without mutating the live repo. The fixture returns a
    callable: `worktree_path = make_git_worktree()` initialises a fresh
    repo each call; pass `commit_message` to control the commit and
    therefore the resulting SHA (different message → different SHA).
    """
    counter = {"n": 0}

    def _make(commit_message="initial"):
        counter["n"] += 1
        repo = tmp_path / f"repo-{counter['n']}"
        repo.mkdir()
        env = {**os.environ,
               "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                       check=True, env=env)
        (repo / "README").write_text(commit_message + "\n")
        subprocess.run(["git", "-C", str(repo), "add", "README"],
                       check=True, env=env)
        subprocess.run(["git", "-C", str(repo), "commit", "-q",
                        "-m", commit_message],
                       check=True, env=env)
        return repo

    return _make


@pytest.fixture
def git_head(make_git_worktree):
    """Return (worktree_path, head_sha) for a fresh tmp repo."""
    def _head(commit_message="initial"):
        repo = make_git_worktree(commit_message=commit_message)
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        return repo, head

    return _head
