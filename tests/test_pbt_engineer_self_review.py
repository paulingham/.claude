"""AC2.7 — `pbt-engineer` has a Self-Review Before Completion section.

Asserts the body contains the five count items (candidates, properties,
counterexamples, justifications, verdict) AND requires the reason code
be reported alongside the verdict for PBT_SKIPPED / PBT_BLOCKED.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"

REQUIRED_ITEMS = (
    "candidate",       # candidate count
    "propert",         # properties authored count (matches "property"/"properties")
    "counterexample",  # counterexamples frozen count
    "justif",          # justifications recorded count
    "verdict",         # verdict emitted
)


def test_agent_has_self_review_checklist():
    body = AGENT_PATH.read_text().lower()
    has_self_review = bool(
        re.search(r"^#+\s+self.review", body, re.MULTILINE | re.IGNORECASE))
    assert has_self_review, (
        "pbt-engineer body must contain a Self-Review section")
    missing = [item for item in REQUIRED_ITEMS if item not in body]
    assert not missing, (
        f"pbt-engineer Self-Review missing items: {missing!r}")
    # Reason-code reporting required for PBT_SKIPPED / PBT_BLOCKED.
    assert "reason" in body and (
        "pbt_skipped" in body or "PBT_SKIPPED".lower() in body), (
        "pbt-engineer Self-Review must require reason code reporting "
        "alongside PBT_SKIPPED / PBT_BLOCKED verdicts")
