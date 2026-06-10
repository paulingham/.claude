"""Guard test: the Default-Opus model pin in CLAUDE.md must name a known-good
Opus model id and must currently be exactly `claude-opus-4-8`.

Why two assertions?
  1. Allowlist check  — catches a future upgrade to an unknown id (typo, new
     generation not yet added to ALLOWED_OPUS_MODELS).
  2. Snapshot check   — catches a silent downgrade (e.g. back to 4-7) that
     would pass the allowlist check but break the expected GA pin.

When a new Opus GA ships and the maintainer updates CLAUDE.md, they MUST also
update EXPECTED_OPUS_PIN below. The allowlist only needs updating when an id
not yet present is used.

Hermetic: stdlib only (re, pathlib, unittest). No subprocess, no network,
no file writes, no process spawning.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Allowlist (test-local SSOT — no shared registry exists in the repo yet).
# To add a newly-released Opus id: append to this set.
# To remove a retired id: delete from this set (and update EXPECTED_OPUS_PIN
# if it was the pinned value).
# ---------------------------------------------------------------------------
ALLOWED_OPUS_MODELS: frozenset = frozenset({
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
})

# Current GA pin. Update this when CLAUDE.md is updated to a new release.
EXPECTED_OPUS_PIN = "claude-opus-4-8"

# Marker used to locate the line in CLAUDE.md (line-number-independent).
_MARKER = "**Default Opus model**"

# Regex that extracts the backtick-quoted model id from the marker line.
_MODEL_ID_RE = re.compile(r"`(claude-[^`]+)`")


def _extract_default_opus_pin(claude_md_text: str) -> tuple[str, list[str]]:
    """Return (model_id, matching_lines) from the Default Opus model line.

    Finds lines containing _MARKER and extracts the first backtick-quoted
    ``claude-...`` id from the first such line.

    Returns:
        model_id:       the extracted id string, or "" if not parseable.
        matching_lines: all lines in the file that contain _MARKER.
    """
    matching_lines = [ln for ln in claude_md_text.splitlines() if _MARKER in ln]
    if not matching_lines:
        return "", matching_lines
    first_line = matching_lines[0]
    match = _MODEL_ID_RE.search(first_line)
    model_id = match.group(1) if match else ""
    return model_id, matching_lines


class DefaultOpusPinMarkerPresence(unittest.TestCase):
    """The '**Default Opus model**' marker must appear exactly once."""

    def test_marker_found_exactly_once(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        _, matching_lines = _extract_default_opus_pin(text)
        self.assertEqual(
            len(matching_lines),
            1,
            f"Expected exactly one line containing '{_MARKER}' in CLAUDE.md; "
            f"found {len(matching_lines)}. "
            f"Matching lines: {matching_lines!r}",
        )


class DefaultOpusPinAllowlist(unittest.TestCase):
    """Pinned model id must be a member of ALLOWED_OPUS_MODELS."""

    def test_pinned_id_is_in_allowed_set(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        model_id, _ = _extract_default_opus_pin(text)
        self.assertIn(
            model_id,
            ALLOWED_OPUS_MODELS,
            f"CLAUDE.md Default Opus model pin '{model_id}' is not in "
            f"ALLOWED_OPUS_MODELS {sorted(ALLOWED_OPUS_MODELS)}. "
            f"If this is a new Opus GA release, add the id to ALLOWED_OPUS_MODELS "
            f"in tests/test_model_pin.py and update EXPECTED_OPUS_PIN.",
        )


class DefaultOpusPinSnapshot(unittest.TestCase):
    """Pinned model id must currently be exactly EXPECTED_OPUS_PIN.

    This snapshot assertion catches silent downgrades (e.g. from 4-8 → 4-7)
    that would pass the allowlist check but violate the expected GA pin.

    When upgrading to a new Opus release:
      1. Update CLAUDE.md line ~13 to the new id.
      2. Update EXPECTED_OPUS_PIN in this file to match.
      3. If the new id is not already in ALLOWED_OPUS_MODELS, add it too.
    """

    def test_pinned_id_matches_expected_ga_release(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        model_id, _ = _extract_default_opus_pin(text)
        self.assertEqual(
            model_id,
            EXPECTED_OPUS_PIN,
            f"CLAUDE.md Default Opus model pin is '{model_id}' but expected "
            f"'{EXPECTED_OPUS_PIN}'. "
            f"If this is intentional (new GA release), update EXPECTED_OPUS_PIN "
            f"in tests/test_model_pin.py to match.",
        )


if __name__ == "__main__":
    unittest.main()
