"""AC2: instinct file exists with required frontmatter + 3-bullet body.

The instinct captures the three v2.1.139 features that look like a fit for the
named migration but are category mismatches. Future intake reads this file via
hooks/_lib/instinct_loader.py and avoids re-investigating.

Plan source: pipeline-state/harness-native-v2140-migration/plan.md § AC2.
Loader contract: hooks/_lib/instinct_loader_helpers.py validates id, confidence,
roles, and a non-empty `## Pattern` body.
"""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTINCT_PATH = (REPO_ROOT
                 / "learning/8efffd88329f34786e1828737702e911/instincts"
                 / "v2.1.139-native-surface-mismatch.md")

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _load_frontmatter_and_body():
    match = _FRONTMATTER.match(INSTINCT_PATH.read_text())
    if not match:
        raise AssertionError(
            f"instinct file at {INSTINCT_PATH} does not have a YAML "
            "frontmatter block delimited by --- markers"
        )
    return yaml.safe_load(match.group(1)), match.group(2)


class InstinctV2139NativeSurfaceMismatch(unittest.TestCase):
    def test_instinct_file_exists_at_canonical_path(self):
        self.assertTrue(
            INSTINCT_PATH.is_file(),
            f"instinct file must exist at {INSTINCT_PATH} "
            "(learning/{project-hash}/instincts/{id}.md convention)",
        )

    def test_instinct_frontmatter_declares_required_fields(self):
        frontmatter, _ = _load_frontmatter_and_body()
        self.assertIsInstance(frontmatter, dict,
                              "frontmatter must parse as a YAML mapping")
        self.assertIsInstance(frontmatter.get("id"), str,
                              "id must be a string")
        confidence = frontmatter.get("confidence")
        self.assertIsInstance(confidence, (int, float),
                              "confidence must be numeric")
        self.assertGreaterEqual(float(confidence), 0.0)
        self.assertLessEqual(float(confidence), 1.0)
        roles = frontmatter.get("roles")
        self.assertIsInstance(roles, list,
                              "roles must be a YAML list")
        self.assertIn("architect", roles,
                      "roles must include architect")
        self.assertIn("infrastructure-engineer", roles,
                      "roles must include infrastructure-engineer")
        self.assertIsInstance(frontmatter.get("domain"), str,
                              "domain must be a string")
        self.assertIsInstance(frontmatter.get("scope"), str,
                              "scope must be a string")

    def test_instinct_body_discusses_three_mismatch_features(self):
        _, body = _load_frontmatter_and_body()
        pattern_match = re.search(
            r"^## Pattern[ \t]*\n(.*?)(?=\n##|\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(pattern_match,
                             "body must contain a `## Pattern` section")
        pattern_body = pattern_match.group(1)
        body_lower = pattern_body.lower()
        self.assertIn("continueonblock", body_lower,
                      "body must discuss `continueOnBlock` mismatch")
        self.assertIn("x-claude-code-agent-id", body_lower,
                      "body must discuss `x-claude-code-agent-id` mismatch")
        self.assertIn("automode.hard_deny", body_lower,
                      "body must reference `autoMode.hard_deny`")
        additive_phrasing = re.search(
            r"additive|belt-and-braces|not a replacement|never a replacement",
            body_lower,
        )
        self.assertIsNotNone(
            additive_phrasing,
            "body must frame autoMode.hard_deny as additive / "
            "belt-and-braces / not-a-replacement",
        )

    def test_instinct_cites_canonical_source(self):
        _, body = _load_frontmatter_and_body()
        citation_anchors = (
            "thinking-defaults.md",
            "agent-protocol.md",
            "code.claude.com/docs/en/hooks",
            "code.claude.com/docs/en/settings",
        )
        self.assertTrue(
            any(anchor in body for anchor in citation_anchors),
            "body must cite at least one canonical source: "
            f"{citation_anchors}",
        )


if __name__ == "__main__":
    unittest.main()
