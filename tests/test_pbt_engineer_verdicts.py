"""AC2.3 — `pbt-engineer` documents the three-verdict contract with reason codes.

Asserts the agent body names PBT_AUTHORED, PBT_SKIPPED, PBT_BLOCKED
with explicit emit conditions; PBT_SKIPPED reason codes
(env-hatch / no-candidates / no-framework-for-language) are documented;
PBT_BLOCKED reason codes (harness-crash / unrecoverable-error) are
documented.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"

VERDICTS = ("PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED")
SKIPPED_REASONS = ("env-hatch", "no-candidates", "no-framework-for-language")
BLOCKED_REASONS = ("harness-crash", "unrecoverable-error")


def test_agent_documents_three_verdict_contract_with_reason_codes():
    body = AGENT_PATH.read_text()
    missing_verdicts = [v for v in VERDICTS if v not in body]
    assert not missing_verdicts, (
        f"pbt-engineer body missing verdicts: {missing_verdicts!r}")
    missing_skipped = [r for r in SKIPPED_REASONS if r not in body]
    assert not missing_skipped, (
        f"pbt-engineer body missing PBT_SKIPPED reason codes: "
        f"{missing_skipped!r}")
    missing_blocked = [r for r in BLOCKED_REASONS if r not in body]
    assert not missing_blocked, (
        f"pbt-engineer body missing PBT_BLOCKED reason codes: "
        f"{missing_blocked!r}")
