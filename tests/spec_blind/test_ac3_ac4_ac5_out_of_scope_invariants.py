"""Spec-blind tests for AC3, AC4, AC5.

AC3 (verbatim): hooks/main-branch-guard.sh unchanged by this branch's commits.
AC4 (verbatim): hooks/_lib/destructive-verbs.txt unchanged by this branch's commits.
AC5 (verbatim): hooks/_lib/thinking_resolver.py, hooks/pre-agent-allowlist.sh,
                hooks/pre-agent-thinking.sh, hooks/_lib/agent_parent_chain.py
                all unchanged by this branch's commits.

User-facing contract:

  * The architect's plan declares this change additive everywhere: the
    autoMode.hard_deny block sits *alongside* the existing destructive-verb
    guard, not in place of it.  If any of the named out-of-scope files moved,
    the spec's "belt-and-braces" guarantee is silently weakened.

  * The "belt working when braces fail" walkthrough (plan § Artifact 4) depends
    on hooks/main-branch-guard.sh and hooks/_lib/destructive-verbs.txt being
    byte-identical to main.  A drift in either file invalidates that recovery
    path for non-auto-mode sessions.

  * The four AC5 files are explicit out-of-scope guards against scope creep
    from items (1), (2), (3) of the original v2.1.139 migration premise (per
    spike-findings): the spike resolution was "drop those, only the additive
    autoMode.hard_deny survives".

Diff is taken against the MERGE BASE of origin/main and HEAD, not against the
current origin/main tip — this matches the build agent's correction in commit
e3d7542 and prevents false failures if main advances mid-pipeline.

These tests were authored WITHOUT reading the build agent's tests at
tests/test_out_of_scope_files_untouched.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


# Files declared out-of-scope by AC3/4/5.
AC3_FILES: tuple[str, ...] = ("hooks/main-branch-guard.sh",)
AC4_FILES: tuple[str, ...] = ("hooks/_lib/destructive-verbs.txt",)
AC5_FILES: tuple[str, ...] = (
    "hooks/_lib/thinking_resolver.py",
    "hooks/pre-agent-allowlist.sh",
    "hooks/pre-agent-thinking.sh",
    "hooks/_lib/agent_parent_chain.py",
)


def _git_available() -> bool:
    return shutil.which("git") is not None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_merge_base(repo: Path) -> str | None:
    """Return the merge-base sha of origin/main..HEAD, or None if origin/main
    isn't available (which happens in air-gapped runs)."""
    rev = _git(repo, "rev-parse", "--verify", "origin/main")
    if rev.returncode != 0:
        return None
    mb = _git(repo, "merge-base", "origin/main", "HEAD")
    if mb.returncode != 0 or not mb.stdout.strip():
        return None
    return mb.stdout.strip()


def _diff_is_empty(repo: Path, ref: str, path: str) -> bool:
    """True iff `git diff --quiet ref..HEAD -- path` reports no changes."""
    res = _git(repo, "diff", "--quiet", f"{ref}..HEAD", "--", path)
    # git diff --quiet returns 0 if no diff, 1 if diff, other on error.
    if res.returncode == 0:
        return True
    if res.returncode == 1:
        return False
    raise AssertionError(
        f"spec-blind: git diff errored on path {path!r} (rc={res.returncode}, "
        f"stderr={res.stderr.strip()!r})"
    )


def _skip_or_merge_base(repo: Path) -> str:
    if not _git_available():
        pytest.skip("git not available in this environment")
    mb = _resolve_merge_base(repo)
    if mb is None:
        pytest.skip(
            "origin/main not available (air-gapped or fresh clone without remote)"
        )
    return mb


@pytest.mark.parametrize("path", AC3_FILES, ids=list(AC3_FILES))
def test_ac3_main_branch_guard_unchanged(repo_root: Path, path: str) -> None:
    """AC3: hooks/main-branch-guard.sh untouched by this branch.

    main-branch-guard.sh is the non-auto-mode destructive-verb enforcer.  If
    this branch touched it, the 'belt-and-braces' walkthrough no longer holds.
    """
    mb = _skip_or_merge_base(repo_root)
    target = repo_root / path
    assert target.is_file(), f"preflight: out-of-scope file missing at {path}"
    assert _diff_is_empty(repo_root, mb, path), (
        f"spec-blind: AC3 violated — {path} was modified on this branch.  "
        f"The autoMode.hard_deny work is supposed to be additive everywhere."
    )


@pytest.mark.parametrize("path", AC4_FILES, ids=list(AC4_FILES))
def test_ac4_destructive_verbs_unchanged(repo_root: Path, path: str) -> None:
    """AC4: hooks/_lib/destructive-verbs.txt untouched by this branch.

    destructive-verbs.txt is the source of truth for non-auto-mode coverage.
    autoMode.hard_deny prose mirrors it but does NOT replace it.
    """
    mb = _skip_or_merge_base(repo_root)
    target = repo_root / path
    assert target.is_file(), f"preflight: out-of-scope file missing at {path}"
    assert _diff_is_empty(repo_root, mb, path), (
        f"spec-blind: AC4 violated — {path} was modified on this branch.  "
        f"Non-auto-mode sessions depend on this file remaining the source of "
        f"truth; any change here breaks the belt-and-braces guarantee."
    )


@pytest.mark.parametrize("path", AC5_FILES, ids=list(AC5_FILES))
def test_ac5_dropped_migration_items_unchanged(repo_root: Path, path: str) -> None:
    """AC5: the four files associated with dropped items (1), (2), (3) of the
    original migration premise must be untouched on this branch.  If any
    moved, the spike's "drop those, keep only autoMode.hard_deny additive"
    resolution has silently grown into scope creep.
    """
    mb = _skip_or_merge_base(repo_root)
    target = repo_root / path
    assert target.is_file(), f"preflight: out-of-scope file missing at {path}"
    assert _diff_is_empty(repo_root, mb, path), (
        f"spec-blind: AC5 violated — {path} was modified on this branch.  "
        f"Scope creep into the dropped migration items (continueOnBlock / "
        f"x-claude-code-agent-id / thinking_resolver rule 2a / parent_chain) "
        f"defeats the spike resolution."
    )


def test_all_out_of_scope_files_unchanged_summary(repo_root: Path) -> None:
    """Cross-cut: name every modified out-of-scope file in a single failure.

    Helpful in CI where parametrized failures may scroll past — this gives the
    operator one consolidated list of what drifted.
    """
    mb = _skip_or_merge_base(repo_root)
    drifted: list[str] = []
    for path in (*AC3_FILES, *AC4_FILES, *AC5_FILES):
        if not _diff_is_empty(repo_root, mb, path):
            drifted.append(path)
    assert not drifted, (
        f"spec-blind: AC3/AC4/AC5 violated — the following out-of-scope files "
        f"were modified on this branch: {drifted}.  The autoMode.hard_deny "
        f"work was supposed to be additive everywhere; any drift here means "
        f"scope creep into the dropped migration items or weakening of the "
        f"belt-and-braces guarantee."
    )
