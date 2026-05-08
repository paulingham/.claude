"""Slice B-AC1: repo-wide audit asserting zero `budget_tokens` usages in
production source.

The audit is a `subprocess.run(["grep", ...])` over `hooks/`, `skills/`,
`agents/`, `scripts/`, and `settings.json`. `tests/` and `pipeline-state/`
are excluded because:

- `tests/` may legitimately reference the rejected `budget_tokens` shape
  while documenting hook-resolver behavior (this very file does so as the
  search literal);
- `pipeline-state/opus47-adapt/` contains intake/plan/scratchpad files
  that discuss the rejected shape descriptively.

The audit IS the evidence — its RED → GREEN transition (which for this
slice is "GREEN on first run because production source is already clean")
is the artifact captured at slice-completion.
"""
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_TARGETS = ["hooks/", "skills/", "agents/", "scripts/", "settings.json"]
EXCLUDE_DIRS = ("--exclude-dir=tests", "--exclude-dir=pipeline-state")


class BudgetTokensAuditNoProductionUsage(unittest.TestCase):
    def test_no_budget_tokens_in_hooks_skills_agents_scripts_settings(self):
        """Slice B-AC1: zero matches for `budget_tokens` outside tests/
        and pipeline-state/.

        `grep -rn` returns exit code 1 when no matches are found, which
        is the success state for this audit. Exit code 0 means at least
        one match was found — that's a contract violation.
        """
        result = subprocess.run(
            ["grep", "-rn", *EXCLUDE_DIRS, "-e", "budget_tokens",
             *SEARCH_TARGETS],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 1,
            msg=("Expected zero `budget_tokens` matches in production "
                 f"source. grep returned exit={result.returncode} with "
                 f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"),
        )
        self.assertEqual(result.stdout, "",
                         msg=f"unexpected matches:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
