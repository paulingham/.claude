"""Slice 1a — Verify CI_GREEN and CI_RED verdict rows exist in the catalog.

AC1: CI_GREEN row present with polarity=success, emitter=pr-creation, phase=ship.
AC2: CI_RED row present with polarity=failure, emitter=pr-creation, phase=ship.

These tests go RED before the rows are added (CI_GREEN / CI_RED absent from catalog),
and GREEN after the rows land in protocols/verdict-catalog.md.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"


def _parse_catalog_rows():
    """Return dict keyed by verdict name -> {polarity, emitters, phase, branch}."""
    rows = {}
    body = CATALOG.read_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    for m in pattern.finditer(body):
        emitter_cell = m.group(3)
        emitters = [
            e.strip().strip("`")
            for e in emitter_cell.split(",")
            if e.strip().strip("`")
        ]
        rows[m.group(1)] = {
            "polarity": m.group(2),
            "emitters": emitters,
            "phase": m.group(4).strip(),
            "branch": m.group(5).strip(),
        }
    return rows


def test_ci_green_row_present_and_well_formed():
    """AC1: CI_GREEN row exists with polarity=success, emitter=pr-creation, phase=ship."""
    rows = _parse_catalog_rows()
    assert "CI_GREEN" in rows, (
        "protocols/verdict-catalog.md must contain a CI_GREEN row "
        "(emitter pr-creation, phase ship). Row is absent."
    )
    row = rows["CI_GREEN"]
    assert row["polarity"] == "success", (
        f"CI_GREEN polarity must be 'success', got: {row['polarity']!r}"
    )
    emitters_str = ", ".join(row["emitters"])
    assert "pr-creation" in emitters_str, (
        f"CI_GREEN emitter must include 'pr-creation', got: {emitters_str!r}"
    )
    assert "ship" in row["phase"], (
        f"CI_GREEN phase must be 'ship', got: {row['phase']!r}"
    )


def test_ci_red_row_present_and_well_formed():
    """AC2: CI_RED row exists with polarity=failure, emitter=pr-creation, phase=ship."""
    rows = _parse_catalog_rows()
    assert "CI_RED" in rows, (
        "protocols/verdict-catalog.md must contain a CI_RED row "
        "(emitter pr-creation, phase ship). Row is absent."
    )
    row = rows["CI_RED"]
    assert row["polarity"] == "failure", (
        f"CI_RED polarity must be 'failure', got: {row['polarity']!r}"
    )
    emitters_str = ", ".join(row["emitters"])
    assert "pr-creation" in emitters_str, (
        f"CI_RED emitter must include 'pr-creation', got: {emitters_str!r}"
    )
    assert "ship" in row["phase"], (
        f"CI_RED phase must be 'ship', got: {row['phase']!r}"
    )
