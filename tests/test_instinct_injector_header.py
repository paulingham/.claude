"""Slice E — instinct-injector.sh stays advisory; header makes that explicit.

The instinct injector is the outlier of the four PreToolUse Agent hooks:
its value-add is *mutation* (splicing a `## Learned Patterns` block into
the prompt), not denial. With `modified_tool_input` schema-absent and
no shell-side DECISION branch, the hook has no enforcement path — the
orchestrator-side splice is the delivery mechanism. The header MUST
make this non-flippability explicit so future maintainers do not
mistake the Path-B template for a one-line `exit 2` flip target.

AC-E1: header contains the literal `DO NOT FLIP TO EXIT 2:` block AND
       three rationale keywords: `mutation-only`, `no DECISION branch`,
       `orchestrator-side splice`.
AC-E2: protocols/autonomous-intelligence.md § Instinct Injection
       cross-references `hooks/instinct-injector.sh`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class DoNotFlipBlockPresentWithThreeReasons(unittest.TestCase):
    def test_do_not_flip_block_present_with_three_reasons(self):
        body = (REPO_ROOT / "hooks" / "instinct-injector.sh").read_text()
        self.assertIn("DO NOT FLIP TO EXIT 2:", body)
        for keyword in ("mutation-only", "no DECISION branch",
                        "orchestrator-side splice"):
            self.assertIn(keyword, body,
                          f"missing rationale keyword: {keyword!r}")


class ProtocolCrossReferencesHook(unittest.TestCase):
    def test_protocol_cross_references_hook(self):
        body = (REPO_ROOT / "protocols" / "autonomous-intelligence.md").read_text()
        self.assertIn("hooks/instinct-injector.sh", body)


if __name__ == "__main__":
    unittest.main()
