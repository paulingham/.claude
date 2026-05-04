"""C62-AC7: autonomous-intelligence.md documents Parent inheritance contract.

Verifies the Per-Agent instinct_categories Contract section explicitly
documents transitive walk semantics + cycle protection.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "rules" / "_detail" / "autonomous-intelligence.md"


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


if __name__ == "__main__":
    unittest.main()
