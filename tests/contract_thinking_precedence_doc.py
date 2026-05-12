"""Tier 0 contract: precedence list ordering in
`protocols/thinking-defaults.md` matches the resolver's actual evaluation
order.

Parses the numbered list under `## Precedence`; asserts the literal sequence
of headers is `1, 2, 2a, 3, 4`. The new tier `2a` slots between `2` (explicit
field) and `3` (role rules); subsequent rules do NOT renumber.

If the ordering drifts (e.g., the architect inserted at the wrong slot, or
the resolver was edited without updating the doc), this contract test fails.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "protocols" / "thinking-defaults.md"

EXPECTED_SEQUENCE = ["1", "2", "2a", "3", "4"]


class PrecedenceListInDocOrders2aBetween2And3(unittest.TestCase):
    def test_precedence_list_in_doc_orders_2a_between_2_and_3(self):
        body = DOC_PATH.read_text()

        # Locate the `## Precedence` section.
        section_match = re.search(
            r"## Precedence(?:\s+\([^)]*\))?\s*\n(.*?)(?=\n## )",
            body,
            re.DOTALL,
        )
        self.assertIsNotNone(
            section_match,
            "## Precedence section not found in thinking-defaults.md",
        )
        section = section_match.group(1)

        # Find every numbered-list header at column 0 (no leading whitespace),
        # tolerating optional `**bold**` wrapping immediately after the number.
        # Pattern handles `1. **`, `2. **`, `2a. **`, etc.
        numbers = re.findall(
            r"(?m)^([0-9]+[a-z]?)\.\s+\*\*",
            section,
        )

        self.assertEqual(
            numbers,
            EXPECTED_SEQUENCE,
            (
                "Precedence list ordering drift in "
                "protocols/thinking-defaults.md.\n"
                f"  expected: {EXPECTED_SEQUENCE}\n"
                f"  observed: {numbers}\n"
                "Rule 2a must slot between rule 2 (explicit field) and "
                "rule 3 (role rules). Subsequent rules do NOT renumber."
            ),
        )


if __name__ == "__main__":
    unittest.main()
