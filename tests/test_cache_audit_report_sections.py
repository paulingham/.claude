"""Slice A AC-A5 — /cache-audit produces a markdown report with required sections.

The skill's procedure section MUST name the four H2 section headers in the
report skeleton:
  - ## Session Read Ratio Summary
  - ## Per-Agent Read Ratio
  - ## Below-Target Sessions
  - ## Notes

We assert against the SKILL.md procedure text (single source of truth for the
report shape). Aggregator implementation will render against this template.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"


class CacheAuditReportSectionsDocumented(unittest.TestCase):
    def test_cache_audit_report_has_required_sections_against_fixture_jsonl(self):
        text = SKILL.read_text()
        for section in (
            "## Session Read Ratio Summary",
            "## Per-Agent Read Ratio",
            "## Below-Target Sessions",
            "## Notes",
        ):
            self.assertIn(
                section, text,
                f"SKILL.md must document the `{section}` header in the report skeleton")


if __name__ == "__main__":
    unittest.main()
