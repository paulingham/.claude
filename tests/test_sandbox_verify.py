"""Tests for the /sandbox-verify skill + sandbox-verify-engineer agent contract.

Covers ACs 3 + 5 from `pipeline-state/workstreams/sandbox-verify/story-1-skill-contract/plan.md`:

- AC3: `emit_skip_if_no_token` (skill no-E2B-token branch) returns
  SANDBOX_SKIPPED with reason `no-e2b-token` AND appends one JSON line to
  `metrics/<session>/sandbox-verify-skips.jsonl`.
- AC5: the seed instinct loads cleanly and intersects the agent's
  `instinct_categories:` set with ≥1 token.

Also includes the Tier 0 frontmatter contract assertion for the new
`skills/sandbox-verify/SKILL.md`.

Env-var test hygiene per `learning/instincts/instinct-env-var-test-hygiene.md`:
mutations of `E2B_API_KEY` use `patch.dict(os.environ, {}, clear=False)`
with the inner `os.environ.pop("E2B_API_KEY", None)` — never bare `pop()`.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from instinct_loader_helpers import parse_file, validate  # noqa: E402
from agent_instinct_categories_loader import (  # noqa: E402
    load_agent_instinct_categories,
)


class SkillFrontmatterDeclaresThreeVerdicts(unittest.TestCase):
    """Tier 0: skill frontmatter declares the three verdicts + canonical fields."""

    def setUp(self):
        self.skill_path = REPO_ROOT / "skills" / "sandbox-verify" / "SKILL.md"

    def test_skill_frontmatter_declares_three_verdicts_and_canonical_fields(self):
        text = self.skill_path.read_text()
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md must have YAML frontmatter")
        fm = yaml.safe_load(match.group(1))

        verdicts = fm.get("verdict", "").split("|")
        self.assertEqual(
            set(verdicts),
            {"SANDBOX_VERIFIED", "SANDBOX_FAILED", "SANDBOX_SKIPPED"},
            "frontmatter `verdict:` must declare exactly the three sandbox verdicts")
        self.assertEqual(fm.get("phase"), "build")
        self.assertEqual(fm.get("dispatch"), "subagent")
        self.assertEqual(fm.get("agent"), "sandbox-verify-engineer")

        body = text[match.end():]
        for heading in ("## When to Invoke", "## Procedure",
                        "## Output", "## Verdict"):
            self.assertIn(heading, body,
                          f"SKILL.md body must contain `{heading}` section")


class SeedInstinctLoadsAndIntersectsAgentCategories(unittest.TestCase):
    """AC5: seed instinct file validates AND its `roles:` intersects the
    agent's `instinct_categories:` with ≥1 token."""

    def test_seed_instinct_loads_and_intersects_agent_categories(self):
        seed_path = REPO_ROOT / "learning" / "instincts" / \
            "sandbox-verify-seed.md"
        self.assertTrue(seed_path.exists(),
                        "seed instinct file must exist for AC5")

        fm, body = parse_file(seed_path)
        self.assertIsNone(
            validate(fm, body),
            "seed instinct must validate per instinct_loader_helpers")

        seed_roles = set(fm["roles"])
        with patch.dict(os.environ,
                        {"CLAUDE_AGENTS_DIR": str(REPO_ROOT / "agents")},
                        clear=False):
            agent_categories = load_agent_instinct_categories(
                "sandbox-verify-engineer")
        self.assertIsInstance(agent_categories, list,
                              "agent `instinct_categories:` must be a YAML list")

        intersection = seed_roles & set(agent_categories)
        self.assertGreaterEqual(
            len(intersection), 1,
            f"seed roles {seed_roles} must intersect agent categories "
            f"{agent_categories} with at least one token")


class SkipWithoutE2BTokenEmitsVerdictAndAppendsJsonl(unittest.TestCase):
    """AC3: invoking the no-E2B-token branch returns SANDBOX_SKIPPED
    with reason `no-e2b-token` AND appends one JSON line to
    `metrics/<session>/sandbox-verify-skips.jsonl`."""

    def test_skip_without_e2b_token_emits_verdict_and_appends_jsonl(self):
        # Import inside the test so a missing module fails as a RED test
        # rather than at collection time.
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = Path(tmp)
            session_id = "test-session-1234"

            # Env-var hygiene: clear=False + inner pop inside patch scope.
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                result = emit_skip_if_no_token(session_id, str(metrics_dir))

            self.assertEqual(result["verdict"], "SANDBOX_SKIPPED",
                             "missing E2B_API_KEY must yield SANDBOX_SKIPPED")
            self.assertEqual(result["reason"], "no-e2b-token",
                             "skip reason must be `no-e2b-token`")

            jsonl_path = (metrics_dir / session_id /
                          "sandbox-verify-skips.jsonl")
            self.assertTrue(jsonl_path.exists(),
                            "skip-log JSONL file must be created")

            lines = jsonl_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1,
                             "exactly one JSONL line must be appended")
            record = json.loads(lines[0])
            self.assertEqual(record["reason"], "no-e2b-token")
            # Timestamp must parse as ISO-8601 (with or without TZ suffix).
            ts = record["timestamp"]
            self.assertRegex(
                ts,
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?"
                r"(Z|[+-]\d{2}:?\d{2})?$",
                "timestamp must parse as ISO-8601")

    def test_skip_appends_one_line_per_call(self):
        """Two consecutive calls must produce two lines.

        Adversarial: kills `O_APPEND` → `O_TRUNC` mutation, which would
        overwrite the file on each call and leave only one line.
        """
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = Path(tmp)
            session_id = "test-session-append"

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                emit_skip_if_no_token(session_id, str(metrics_dir))
                emit_skip_if_no_token(session_id, str(metrics_dir))

            jsonl_path = (metrics_dir / session_id /
                          "sandbox-verify-skips.jsonl")
            self.assertTrue(jsonl_path.exists())
            lines = jsonl_path.read_text().splitlines()
            self.assertEqual(
                len(lines), 2,
                "two calls must produce two lines (append semantics)")

    def test_skip_jsonl_ends_with_newline(self):
        """JSONL line discipline: file content ends with `\\n`.

        Adversarial: kills the drop-newline mutation, which produces
        content that cannot be safely concatenated with future appends.
        """
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = Path(tmp)
            session_id = "test-session-newline"

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                emit_skip_if_no_token(session_id, str(metrics_dir))

            jsonl_path = (metrics_dir / session_id /
                          "sandbox-verify-skips.jsonl")
            content = jsonl_path.read_bytes()
            self.assertTrue(
                content.endswith(b"\n"),
                "JSONL line discipline: file content must end with `\\n`")

    def test_skip_record_uses_canonical_reason_key(self):
        """The persisted record uses key `reason` exactly.

        Adversarial: kills case-mangled key mutations like `REASON`.
        """
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = Path(tmp)
            session_id = "test-session-canonical"

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                emit_skip_if_no_token(session_id, str(metrics_dir))

            jsonl_path = (metrics_dir / session_id /
                          "sandbox-verify-skips.jsonl")
            record = json.loads(jsonl_path.read_text().splitlines()[0])
            self.assertIn(
                "reason", record,
                "persisted record MUST use the exact key `reason`")
            self.assertNotIn(
                "REASON", record,
                "persisted record key must be lowercase `reason`")


if __name__ == "__main__":
    unittest.main()
