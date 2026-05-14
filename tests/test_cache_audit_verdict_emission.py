"""Slice A AC-A6 — /cache-audit always emits CACHE_AUDIT_READY on success.

The verdict survives the empty-metrics case (no cache.jsonl files found —
report still writes with empty-state notes). Asserted by static read of the
SKILL.md "Verdict" stanza in the Output Format section.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"


class CacheAuditVerdictEmission(unittest.TestCase):
    def test_cache_audit_emits_ready_verdict_on_empty_metrics_dir(self):
        text = SKILL.read_text()
        # Frontmatter declares it.
        self.assertTrue(
            re.search(r'^verdict:\s*"?CACHE_AUDIT_READY"?\s*$', text, re.MULTILINE),
            "Frontmatter must declare verdict: CACHE_AUDIT_READY")
        # Procedure section documents the empty-state path.
        self.assertTrue(
            re.search(r"empty.+CACHE_AUDIT_READY|CACHE_AUDIT_READY.+empty", text),
            "SKILL.md procedure must document that the empty-metrics case "
            "still emits CACHE_AUDIT_READY")
        # `Verdict: CACHE_AUDIT_READY` body line is present.
        self.assertTrue(
            re.search(r"^Verdict:\s*CACHE_AUDIT_READY\s*$", text, re.MULTILINE),
            "SKILL.md must contain a `Verdict: CACHE_AUDIT_READY` body line")


if __name__ == "__main__":
    unittest.main()
