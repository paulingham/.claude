"""Slice B-AC2 + B-AC3: doc-rendering tests for the new `## Adaptive
Thinking (Opus 4.7+)` subsection in `protocols/thinking-defaults.md`.

The subsection sits between `## Fields` and `## Precedence`. Three tests:

- B-AC2 (structure): subsection exists, body contains `budget_tokens`,
  `400`, `type: "adaptive"`.
- B-AC2 (verbatim quote): subsection contains the most stable Anthropic-
  source phrase: `manual extended thinking is no longer supported`.
- B-AC3 (guidance + hook-profile + URL): subsection contains a "do not
  introduce" / "do not set" guidance phrase, the verified URL
  `platform.claude.com/docs/en/build-with-claude/extended-thinking`, and
  the `CLAUDE_HOOK_PROFILE=minimal` interaction note.
"""
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "thinking-defaults.md"
SUBSECTION_HEADER = "## Adaptive Thinking (Opus 4.7+)"


def _adaptive_thinking_subsection_body() -> str:
    """Return the body of the `## Adaptive Thinking (Opus 4.7+)` subsection.

    Body runs from the header to the next top-level `## ` heading. Returns
    empty string if the subsection is missing.
    """
    text = DOC.read_text()
    pattern = re.escape(SUBSECTION_HEADER) + r"(.+?)(?=\n##\s+|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


class AdaptiveThinkingSubsectionStructure(unittest.TestCase):
    def test_thinking_defaults_has_adaptive_thinking_subsection(self):
        """B-AC2: subsection exists between `## Fields` and `## Precedence`
        and body contains the structural substrings."""
        text = DOC.read_text()
        self.assertIn(SUBSECTION_HEADER, text,
                      msg="`## Adaptive Thinking (Opus 4.7+)` header missing")

        # Verify ordering: Fields → Adaptive Thinking → Precedence.
        fields_pos = text.index("## Fields")
        adaptive_pos = text.index(SUBSECTION_HEADER)
        precedence_pos = text.index("## Precedence")
        self.assertLess(fields_pos, adaptive_pos,
                        msg="`## Adaptive Thinking` must follow `## Fields`")
        self.assertLess(adaptive_pos, precedence_pos,
                        msg="`## Adaptive Thinking` must precede `## Precedence`")

        body = _adaptive_thinking_subsection_body()
        self.assertIn("budget_tokens", body,
                      msg="subsection must reference `budget_tokens`")
        self.assertIn("400", body,
                      msg="subsection must reference HTTP 400")
        self.assertIn('type: "adaptive"', body,
                      msg='subsection must reference `type: "adaptive"`')


class AdaptiveThinkingSubsectionQuotesAnthropicSource(unittest.TestCase):
    def test_adaptive_thinking_subsection_quotes_anthropic_source_verbatim(self):
        """B-AC2: subsection quotes the most stable Anthropic-source phrase
        verbatim. The phrase appears in all three architect-captured
        verbatim quotes (Source Verification § plan.md)."""
        body = _adaptive_thinking_subsection_body()
        self.assertIn(
            "manual extended thinking is no longer supported", body,
            msg=("subsection must quote the verbatim phrase "
                 "`manual extended thinking is no longer supported` "
                 "from the Anthropic source"),
        )


class AdaptiveThinkingSubsectionGuidance(unittest.TestCase):
    def test_adaptive_thinking_subsection_warns_against_budget_tokens_and_notes_hook_profile(self):
        """B-AC3: subsection includes a `do not introduce`/`do not set`
        guidance phrase, cites the Anthropic URL, and notes the
        `CLAUDE_HOOK_PROFILE=minimal` interaction."""
        body = _adaptive_thinking_subsection_body()

        # Guidance phrase — accept either form, case-insensitive.
        guidance_pattern = re.compile(
            r"do\s+not\s+(?:introduce|set)", re.IGNORECASE)
        self.assertRegex(
            body, guidance_pattern,
            msg=("subsection must contain `do not introduce` or "
                 "`do not set` guidance phrase"),
        )

        # Verified Anthropic URL must appear.
        self.assertIn(
            "platform.claude.com/docs/en/build-with-claude/extended-thinking",
            body,
            msg=("subsection must cite the verified Anthropic URL "
                 "`platform.claude.com/docs/en/build-with-claude/"
                 "extended-thinking`"),
        )

        # Hook-profile interaction note.
        self.assertIn(
            "CLAUDE_HOOK_PROFILE=minimal", body,
            msg=("subsection must note the "
                 "`CLAUDE_HOOK_PROFILE=minimal` interaction"),
        )


if __name__ == "__main__":
    unittest.main()
