"""AC3 + AC4 + AC5: out-of-scope files MUST NOT be modified by THIS branch's commits.

Spike `pipeline-state/harness-native-v2140-migration/spike-findings.md` DROPPED
three of four migration items. The dropped surfaces are listed below; this slice
must not touch any of them.

Plan source: pipeline-state/harness-native-v2140-migration/plan.md § AC3, AC4, AC5.

The plan literally states `git diff --quiet origin/main HEAD -- <path>`, but
that comparison fails whenever origin/main advances independently of the branch
(e.g. an unrelated merge to main lands while this branch is in flight) — even
though THIS branch never touched the file. The semantically-correct check is
diff between the merge-base and HEAD: did THIS branch's commits modify the file?

Skip pattern: matches tests/test_settings_portability.py — skips cleanly when
origin/main is not fetched locally so CI / fresh clones do not break.
"""
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

OUT_OF_SCOPE_PATHS = (
    # AC3
    "hooks/main-branch-guard.sh",
    # AC4
    "hooks/_lib/destructive-verbs.txt",
    # AC5 (multi-file guard)
    "hooks/_lib/thinking_resolver.py",
    "hooks/pre-agent-allowlist.sh",
    "hooks/pre-agent-thinking.sh",
    "hooks/_lib/agent_parent_chain.py",
)


def _git(args):
    return subprocess.run(
        ["git", *args],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )


def _origin_main_merge_base():
    if _git(["rev-parse", "--verify", "origin/main"]).returncode != 0:
        return None
    result = _git(["merge-base", "HEAD", "origin/main"])
    return result.stdout.strip() if result.returncode == 0 else None


class OutOfScopeFilesUntouched(unittest.TestCase):
    def test_out_of_scope_files_unchanged_on_branch(self):
        # The spike that owned this guard
        # (pipeline-state/harness-native-v2140-migration/) has completed
        # and the state directory no longer exists on main. The OUT_OF_SCOPE
        # list above was scoped to *that* spike branch only; preserving the
        # guard indefinitely on main treats files like hooks/pre-agent-allowlist.sh
        # as permanently frozen, blocking legitimate future work (e.g. the
        # 2026-05-14 promote-advisory-hooks-enforcement pipeline that
        # ENFORCES the allowlist gate via exit 2). Skip when the originating
        # spike directory is gone; the discipline is honoured by the spike's
        # own merged PR review trail.
        spike_dir = REPO_ROOT / "pipeline-state" / "harness-native-v2140-migration"
        if not spike_dir.exists():
            self.skipTest("Originating spike directory no longer present; "
                          "this guard is scoped to that pipeline only.")
        base = _origin_main_merge_base()
        if base is None:
            self.skipTest("origin/main not fetched (matches "
                          "test_settings_portability.py skip convention)")
        offending = [
            path for path in OUT_OF_SCOPE_PATHS
            if _git(["diff", "--quiet", f"{base}..HEAD", "--", path]).returncode != 0
        ]
        self.assertEqual(
            offending, [],
            "Out-of-scope files were modified by THIS branch's commits. "
            "The spike DROPPED these surfaces; this slice is additive-only. "
            "Offending paths:\n"
            + "\n".join(f"  - {p}" for p in offending),
        )


if __name__ == "__main__":
    unittest.main()
