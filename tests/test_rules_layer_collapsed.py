"""Regression: rules/ stub layer collapsed to core.md (+ WS-B gear-tier split); verdict-catalog in protocols/.

Asserts the structural invariants after WS-C, updated for the Phase B
gear-aware rules split (rules/core.md becomes a thin index over
rules/safety.md + rules/pipeline-rigour.md; see rules/core.md itself):
1. protocols/verdict-catalog.md exists and rules/verdict-catalog.md does NOT.
2. rules/ contains exactly {"core.md", "safety.md", "pipeline-rigour.md"} —
   none of the 12 pre-WS-C stubs remain, and no other file has crept in.
3. The live harness-audit verdict resolver reads the catalog from its new location
   in protocols/ and resolves cleanly (exit code 0).
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import verdict_consistency  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Structural move: verdict-catalog is in protocols/, not rules/
# ---------------------------------------------------------------------------

def test_verdict_catalog_in_protocols():
    """protocols/verdict-catalog.md must exist after the move."""
    assert (REPO_ROOT / "protocols" / "verdict-catalog.md").is_file(), (
        "protocols/verdict-catalog.md not found — was it moved correctly?"
    )


def test_verdict_catalog_not_in_rules():
    """rules/verdict-catalog.md must NOT exist after the move."""
    assert not (REPO_ROOT / "rules" / "verdict-catalog.md").exists(), (
        "rules/verdict-catalog.md still exists — it was not removed"
    )


# ---------------------------------------------------------------------------
# 2. Collapse invariant: rules/ contains exactly the WS-C core.md plus the
#    Phase B gear-tier split (safety.md + pipeline-rigour.md).
# ---------------------------------------------------------------------------

def test_rules_contains_only_core_md():
    """rules/ must contain exactly core.md, safety.md, and pipeline-rigour.md."""
    rules_dir = REPO_ROOT / "rules"
    assert rules_dir.is_dir(), "rules/ directory missing"
    contents = set(os.listdir(rules_dir))
    assert contents == {"core.md", "safety.md", "pipeline-rigour.md"}, (
        f"rules/ must contain exactly {{core.md, safety.md, pipeline-rigour.md}}, "
        f"found: {sorted(contents)}"
    )


def test_none_of_the_12_stubs_remain():
    """Each of the 12 deleted stub files must not exist under rules/."""
    stubs = [
        "agent-protocol.md",
        "atdd-procedure.md",
        "autonomous-intelligence.md",
        "e2e-protocol.md",
        "engineering-invariants.md",
        "module-boundaries-protocol.md",
        "multi-repo-protocol.md",
        "operational-protocol.md",
        "parallel-dispatch-protocol.md",
        "pipeline-protocol.md",
        "reflection-protocol.md",
        "thinking-defaults.md",
    ]
    still_present = [s for s in stubs if (REPO_ROOT / "rules" / s).exists()]
    assert not still_present, (
        f"Stub files still present under rules/: {still_present}"
    )


# ---------------------------------------------------------------------------
# 3. Harness-audit resolver: reads from protocols/ and returns clean
# ---------------------------------------------------------------------------

def test_harness_audit_resolves_verdicts_from_protocols():
    """verdict_consistency.check() must exit 0 against this repo root."""
    code, diag = verdict_consistency.check(REPO_ROOT)
    assert code == 0, f"verdict resolution failed: {diag}"


def test_resolver_reads_relocated_catalog():
    """The live resolver's CATALOG attribute must point to protocols/verdict-catalog.md."""
    canonical = verdict_consistency._import_canonical(REPO_ROOT)
    catalog_path = canonical.CATALOG
    assert str(catalog_path).endswith("protocols/verdict-catalog.md"), (
        f"Resolver CATALOG does not end in protocols/verdict-catalog.md: {catalog_path}"
    )
    assert catalog_path.is_file(), (
        f"Resolver CATALOG path does not exist as a file: {catalog_path}"
    )
