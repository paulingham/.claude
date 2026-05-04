"""C3 — Internal Eval Gate verdict captured for this branch (AC33, H3).

Build agent at S7 invokes `/internal-eval run` and writes the verdict to
`pipeline-state/web-e2e-playwright/internal-eval.txt`. This test reads
that file and asserts the verdict is `EVAL_PASSED`.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_FILE = (REPO_ROOT / "pipeline-state" / "web-e2e-playwright"
             / "internal-eval.txt")


def test_internal_eval_run_returns_eval_passed_for_this_branch():
    """AC33 (H3): pipeline-state/web-e2e-playwright/internal-eval.txt == 'EVAL_PASSED'."""
    assert EVAL_FILE.exists(), (
        f"Internal Eval Gate verdict missing: expected file at {EVAL_FILE}. "
        "Build agent at S7 must invoke `/internal-eval run` and capture "
        "verdict.")
    content = EVAL_FILE.read_text().strip()
    assert content == "EVAL_PASSED", (
        f"Internal Eval Gate verdict was `{content}` (expected "
        f"`EVAL_PASSED`). Regression — fix before merge.")
