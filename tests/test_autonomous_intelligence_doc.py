"""C62-AC7: autonomous-intelligence.md documents Parent inheritance contract.

Verifies the Per-Agent instinct_categories Contract section explicitly
documents transitive walk semantics + cycle protection.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"


def _per_agent_section():
    text = DOC.read_text()
    match = re.search(
        r"####\s+Per-agent[^\n]*instinct_categories[^\n]*contract\b(.+?)"
        r"(?=\n#### |\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


class ParentChainContractDocumentsUnionSemantics(unittest.TestCase):
    def test_per_agent_categories_contract_documents_parent_walked_transitively(self):
        body = _per_agent_section()
        self.assertTrue(body, "Per-agent contract section not found")
        self.assertIn("Parent inheritance", body)
        self.assertIn("walked transitively", body)
        self.assertIn("union", body.lower())
        self.assertIn("visited-set", body)




def _instinct_injection_section():
    text = DOC.read_text()
    match = re.search(
        r"##\s+1\.\s+Pipeline Scratchpad\b|"
        r"###\s+Instinct Injection\b(.+?)"
        r"(?=\n###\s+|\n##\s+|\Z)", text, re.DOTALL)
    # Use a more permissive locator
    match = re.search(
        r"###\s+Instinct Injection\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _promotion_section():
    text = DOC.read_text()
    match = re.search(
        r"###\s+Scratchpad[^\n]*Instinct Promotion\b(.+?)"
        r"(?=\n###\s+|\n##\s+|\Z)", text, re.DOTALL)
    return match.group(1) if match else ""


_PREFER_OPUS_CAVEAT = (
    "Not yet implemented \u2014 `/harness:learn` writer and orchestrator "
    "reader deferred to the next learning slice.")


class PreferOpusContractDocumentedWithDeferralCaveat(unittest.TestCase):
    def test_instinct_injection_section_documents_prefer_opus_with_caveat(self):
        body = _instinct_injection_section()
        self.assertTrue(body, "Instinct Injection section not found")
        self.assertIn("Executor Override (prefer_opus)", body)
        self.assertIn("\u22653 pipelines", body)
        self.assertIn("Sonnet executor", body)
        self.assertIn("\u22652 review rounds", body)
        self.assertIn(_PREFER_OPUS_CAVEAT, body)


class PreferOpusPromotionDocumentedWithDeferralCaveat(unittest.TestCase):
    def test_promotion_section_lists_prefer_opus_trigger_with_caveat(self):
        body = _promotion_section()
        self.assertTrue(body, "Promotion section not found")
        self.assertIn("prefer_opus: true", body)
        self.assertIn("deferred", body)


if __name__ == "__main__":
    unittest.main()
