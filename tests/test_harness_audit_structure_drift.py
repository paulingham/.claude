"""C3 — local structure-drift check on rules/_detail/e2e-protocol.md (AC32, H2).

Reimplements the relevant portion of `/harness-audit` Step 2c (`STRUCTURE_OK`):
- Frontmatter present and parseable
- Required headings present and in correct hierarchy
- No orphan sections (post-restructure shape is Targets > Mobile + Web,
  Shared Verdict Semantics, Incident Context).
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = REPO_ROOT / "rules" / "_detail" / "e2e-protocol.md"

REQUIRED_H2 = ("Targets", "Shared Verdict Semantics")
REQUIRED_H3_UNDER_TARGETS = (
    "Mobile (Maestro)",
    "Web (Playwright / Cypress)",
)


def _read():
    return PROTOCOL.read_text()


def test_frontmatter_present_and_parseable():
    """AC32 (a): frontmatter intact + parseable as YAML."""
    text = _read()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, "e2e-protocol.md missing YAML frontmatter"
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict), "Frontmatter is not a YAML mapping"
    assert "paths" in parsed, "Frontmatter missing `paths:` field"
    assert isinstance(parsed["paths"], list), "`paths:` must be a YAML list"


def test_paths_frontmatter_includes_web_and_mobile_globs():
    """AC32 (b, R5): paths frontmatter unions web + mobile globs."""
    text = _read()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    parsed = yaml.safe_load(match.group(1))
    paths = parsed["paths"]
    text_paths = "\n".join(paths)
    # Mobile globs preserved.
    assert "maestro/" in text_paths or any(
        "maestro" in p for p in paths), \
        "Mobile/maestro path glob lost from frontmatter"
    # Web globs unioned in (R5).
    has_web = any(re.search(r"middleware|Auth|checkout|sw\.|playwright|"
                            r"cypress|\*Form|forms|payment|iframe|widgets|"
                            r"workbox|service-worker", p)
                  for p in paths)
    assert has_web, ("Web globs not unioned into frontmatter `paths:` "
                     "(R5 mitigation missing)")


def test_required_h2_headings_present():
    """AC32 (c): required H2 headings present."""
    text = _read()
    for heading in REQUIRED_H2:
        assert re.search(r"^##\s+" + re.escape(heading) + r"\s*$",
                         text, re.MULTILINE), \
            f"Required H2 `## {heading}` missing from e2e-protocol.md"


def test_required_h3_under_targets():
    """AC32 (d): required H3 subsections under `## Targets`."""
    text = _read()
    # Extract Targets body.
    match = re.search(r"^##\s+Targets\s*\n(.*?)(?=\n##\s+|\Z)",
                      text, re.MULTILINE | re.DOTALL)
    assert match, "Could not locate `## Targets` section body"
    body = match.group(1)
    for sub in REQUIRED_H3_UNDER_TARGETS:
        # Use `\s*$` rather than `\b` because `\b` does not match
        # between `)` and `\n` (both non-word).
        assert re.search(r"^###\s+" + re.escape(sub) + r"\s*$",
                         body, re.MULTILINE), \
            f"Required `### {sub}` missing under `## Targets`"


def test_no_orphan_top_level_headings():
    """AC32 (e): no top-level headings outside the canonical list.

    Canonical H2 set: Targets, Shared Verdict Semantics, Incident Context.
    """
    text = _read()
    canonical = {"Targets", "Shared Verdict Semantics", "Incident Context"}
    found = set()
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            found.add(m.group(1).strip())
    orphans = found - canonical
    assert not orphans, (
        f"Orphan top-level headings found in e2e-protocol.md: {orphans}. "
        f"Canonical set: {canonical}")


def test_incident_context_preserved():
    """AC32 (f): Incident Context section preserved post-restructure."""
    text = _read()
    assert re.search(r"^##\s+Incident Context\b", text, re.MULTILINE), \
        "`## Incident Context` section lost in restructure"
