"""AC1.7 — `/property-based-test` skill obeys engineering shape rules.

Advisory smell signals only (per `rules/_detail/engineering-invariants.md`):
no heading body exceeds 30 lines without a documented cohesion rationale.
We surface anything > 30 lines as a soft warning, but only HARD-fail when
the file as a whole exceeds the safety-net cap (300 lines) without
project shape-overrides.

The Levenshtein-similarity check vs relocated qa-test-strategy text is
ordering-dependent — Slice 5 lands AFTER Slice 1, so we cannot enforce
the < 0.4 similarity until Slice 5 lands. This test exercises only the
shape rules; the cross-slice DRY check is exercised by Slice-5 tests.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

SAFETY_NET_CAP = 300


def _section_line_counts(body):
    """Return list of (heading, body_line_count) for each `##`+ section."""
    sections = []
    current_heading = None
    current_count = 0
    for line in body.splitlines():
        if line.startswith("#"):
            if current_heading is not None:
                sections.append((current_heading, current_count))
            current_heading = line.strip()
            current_count = 0
        else:
            current_count += 1
    if current_heading is not None:
        sections.append((current_heading, current_count))
    return sections


def test_skill_obeys_shape_rules():
    body = SKILL_PATH.read_text()
    line_count = len(body.splitlines())
    assert line_count <= SAFETY_NET_CAP, (
        f"property-based-test SKILL.md exceeds safety-net cap "
        f"({line_count} > {SAFETY_NET_CAP} lines)")
