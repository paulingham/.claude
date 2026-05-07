"""AC5 + AC18 — product-reviewer consumes screenshots ONLY.

AC5 (negative): in the Inputs and Responsibilities sections, the document
must NOT match `a11y/.*\\.json` paths or `assertion A[1-6]` references.

AC18 (positive): a non-responsibility line must explicitly name
`a11y JSON` as out-of-scope.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_REVIEWER = REPO_ROOT / "agents" / "product-reviewer.md"


def _section(text, name):
    """Extract content of a `## <name>` section."""
    pat = re.compile(
        rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1) if m else ""


class ProductReviewerA11yJsonOutOfScope(unittest.TestCase):
    """AC5 — Inputs/Responsibilities sections free of a11y JSON references."""

    def test_inputs_section_does_not_reference_a11y_json_paths(self):
        text = PRODUCT_REVIEWER.read_text()
        section = _section(text, "Inputs")
        # The forbidden pattern is a11y JSON FILE PATHS / consumption,
        # not the literal phrase "a11y JSON" in a non-responsibility line.
        # AC5 forbids `a11y/*.json` paths.
        self.assertNotRegex(section, r"a11y/[^\s]*\.json")

    def test_responsibilities_section_does_not_reference_assertion_ids(self):
        text = PRODUCT_REVIEWER.read_text()
        responsibilities = _section(text, "Responsibilities")
        self.assertNotRegex(
            responsibilities, r"assertion A[1-6]", )


class ProductReviewerExplicitlyNamesA11yJsonOutOfScope(unittest.TestCase):
    """AC18 — a11y JSON named explicitly as out-of-scope somewhere."""

    def test_some_section_states_a11y_json_is_out_of_scope(self):
        text = PRODUCT_REVIEWER.read_text()
        # Either Responsibilities or Inputs MUST contain the
        # out-of-scope statement naming a11y JSON.
        responsibilities = _section(text, "Responsibilities")
        inputs = _section(text, "Inputs")
        combined = responsibilities + "\n" + inputs
        self.assertRegex(
            combined, r"a11y JSON",
            "product-reviewer must positively name 'a11y JSON' as "
            "out-of-scope in Responsibilities or Inputs (AC18)")
        # And the line must use 'NOT' or 'out-of-scope' wording.
        self.assertRegex(
            combined, r"(?:NOT|not)\s+(?:consume|score|evaluate|read)|"
            r"out-of-scope|out of scope",
            "the a11y JSON reference must read as a non-responsibility")


if __name__ == "__main__":
    unittest.main()
