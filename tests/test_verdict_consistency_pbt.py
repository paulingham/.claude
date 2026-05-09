"""AC3.2 — `/harness-audit` verdict-consistency passes after PBT addition.

We re-use the catalog parser and skill-verdict extractor from
`tests/test_verdict_catalog_audit.py` directly to assert forward and
reverse drift is zero for the three new PBT verdicts.
"""
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _audit_module():
    """Lazy import to avoid hard coupling to import order."""
    return importlib.import_module("tests.test_verdict_catalog_audit")


def test_verdict_consistency_passes_after_pbt_addition():
    """Forward + reverse: every PBT verdict resolves; emitter resolves."""
    audit = _audit_module()
    rows = audit._parse_catalog_rows()
    catalog_verdicts = {r["verdict"] for r in rows}
    new_verdicts = {"PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED"}
    missing = new_verdicts - catalog_verdicts
    assert not missing, (
        f"PBT verdicts not yet in catalog: {missing}")

    # The catalog rows for these verdicts must resolve to the
    # property-based-test skill.
    pbt_rows = [r for r in rows if r["verdict"] in new_verdicts]
    for row in pbt_rows:
        assert "property-based-test" in row["emitters"], (
            f"PBT row emitter mismatch: {row}")

    # Reverse: the skill file's verdict declarations match the catalog.
    skill_path = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"
    skill_verdicts = audit._skill_verdicts(skill_path)
    forward_drift = [v for v in skill_verdicts if v not in catalog_verdicts]
    assert not forward_drift, (
        f"property-based-test skill emits verdicts missing from catalog: "
        f"{forward_drift}")
