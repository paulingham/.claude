"""AC3 + AC4 + AC5: out-of-scope files MUST remain byte-identical to origin/main.

Spike `pipeline-state/harness-native-v2140-migration/spike-findings.md` DROPPED
three of four migration items. The dropped surfaces are listed below; this slice
must not touch any of them.

Plan source: pipeline-state/harness-native-v2140-migration/plan.md § AC3, AC4, AC5.
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


def _origin_main_available() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    return result.returncode == 0


class OutOfScopeFilesUntouched(unittest.TestCase):
    def test_out_of_scope_files_unchanged_on_branch(self):
        if not _origin_main_available():
            self.skipTest("origin/main not fetched (matches "
                          "test_settings_portability.py skip convention)")
        offending = []
        for path in OUT_OF_SCOPE_PATHS:
            result = subprocess.run(
                ["git", "diff", "--quiet", "origin/main", "--", path],
                capture_output=True, text=True, check=False, cwd=REPO_ROOT,
            )
            if result.returncode != 0:
                offending.append(path)
        self.assertEqual(
            offending, [],
            "Out-of-scope files were modified on this branch. The spike DROPPED "
            "these surfaces; this slice is additive-only. Offending paths:\n"
            + "\n".join(f"  - {p}" for p in offending),
        )


if __name__ == "__main__":
    unittest.main()
