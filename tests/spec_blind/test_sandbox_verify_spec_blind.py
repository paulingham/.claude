"""
Spec-blind behavioural tests for Story 1 of the sandbox-verify epic.

These tests are authored from the AC list + public API surface ONLY.
They do NOT import from `src/` or read `hooks/_lib/*.py` bodies.
The validator's value depends on cross-validating the build-time tests
without being contaminated by the same misconceptions the production
code may carry.

Public surfaces exercised:
  - `skills/sandbox-verify/SKILL.md` (frontmatter contract)
  - `agents/sandbox-verify-engineer.md` (tools allowlist + instinct_categories)
  - `protocols/verdict-catalog.md` (registered verdicts table)
  - `learning/instincts/sandbox-verify-seed.md` (seed instinct frontmatter)
  - `hooks/_lib/sandbox_verify_diff.py:compare_pass_sets(worktree, sandbox)`
  - `hooks/_lib/sandbox_verify_skip.py:emit_skip_if_no_token(session_id, metrics_dir)`
  - `hooks/_lib/agent_tools_loader.py:load_agent_tools(role)`
  - `hooks/_lib/instinct_loader_helpers.py:parse_file(path)` + `validate(record)`
  - `hooks/_lib/agent_instinct_categories_loader.py:load_agent_instinct_categories(role)`

NO `src/` reads. NO `hooks/_lib/*.py` body reads.
"""

import datetime
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


# ---------------------------------------------------------------------------
# AC1 — Verdict catalog contract: three rows registered with correct shape.
# ---------------------------------------------------------------------------

class AC1VerdictCatalogTest(unittest.TestCase):
    """AC1: protocols/verdict-catalog.md contains exactly three SANDBOX_* rows.

    Each row: emitter=`sandbox-verify`, phase=`build`, polarity matches
    success/failure/info for SANDBOX_VERIFIED/FAILED/SKIPPED respectively.
    """

    # Catalog row regex pinned by the project's existing parser; mirrors
    # `tests/test_verdict_catalog_consistency.py`'s established shape (the
    # SKILL.md plan documents this as the canonical regex). Spec-blind reads
    # ONLY the catalog file itself — not the regex test.
    _ROW_RE = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|\s*`([^`]+)`\s*\|\s*([a-z\- ]+)\s*\|"
    )

    @classmethod
    def setUpClass(cls):
        catalog_path = REPO_ROOT / "protocols" / "verdict-catalog.md"
        cls.catalog_text = catalog_path.read_text(encoding="utf-8")

    def _find_row(self, verdict_name):
        for line in self.catalog_text.splitlines():
            m = self._ROW_RE.match(line)
            if m and m.group(1) == verdict_name:
                return {
                    "verdict": m.group(1),
                    "polarity": m.group(2),
                    "emitter": m.group(3),
                    "phase": m.group(4).strip(),
                }
        return None

    def test_sandbox_verified_row_present_with_success_polarity(self):
        row = self._find_row("SANDBOX_VERIFIED")
        self.assertIsNotNone(row, "SANDBOX_VERIFIED row not found in catalog")
        self.assertEqual(row["polarity"], "success")
        self.assertEqual(row["emitter"], "sandbox-verify")
        self.assertEqual(row["phase"], "build")

    def test_sandbox_failed_row_present_with_failure_polarity(self):
        row = self._find_row("SANDBOX_FAILED")
        self.assertIsNotNone(row, "SANDBOX_FAILED row not found in catalog")
        self.assertEqual(row["polarity"], "failure")
        self.assertEqual(row["emitter"], "sandbox-verify")
        self.assertEqual(row["phase"], "build")

    def test_sandbox_skipped_row_present_with_info_polarity(self):
        row = self._find_row("SANDBOX_SKIPPED")
        self.assertIsNotNone(row, "SANDBOX_SKIPPED row not found in catalog")
        self.assertEqual(row["polarity"], "info")
        self.assertEqual(row["emitter"], "sandbox-verify")
        self.assertEqual(row["phase"], "build")

    def test_exactly_three_sandbox_rows_present(self):
        sandbox_pattern = re.compile(r"^SANDBOX_(VERIFIED|FAILED|SKIPPED)$")
        found = set()
        for line in self.catalog_text.splitlines():
            m = self._ROW_RE.match(line)
            if m and sandbox_pattern.match(m.group(1)):
                found.add(m.group(1))
        self.assertEqual(
            found,
            {"SANDBOX_VERIFIED", "SANDBOX_FAILED", "SANDBOX_SKIPPED"},
            f"Expected exactly three SANDBOX_* rows; got {sorted(found)}",
        )


# ---------------------------------------------------------------------------
# AC2 — Agent tools allowlist: exactly [Read, Grep, Glob, Bash], in order,
# with no Write/Edit/MultiEdit/Agent/Skill.
# ---------------------------------------------------------------------------

class AC2AgentToolsAllowlistTest(unittest.TestCase):
    """AC2: agents/sandbox-verify-engineer.md tools allowlist is exactly
    [Read, Grep, Glob, Bash] in order (snapshot semantics).

    `agent_tools_loader.load_agent_tools` resolves the agent file via the
    `CLAUDE_AGENTS_DIR` env-var override (documented in CLAUDE.md). Spec-blind
    tests run from the worktree; we point the loader at the worktree's
    agents/ directory so the loader can find the candidate build's agent file.
    """

    def _worktree_agents_dir(self):
        return str(REPO_ROOT / "agents")

    def test_load_agent_tools_returns_exact_ordered_list(self):
        from agent_tools_loader import load_agent_tools

        with patch.dict(os.environ, {"CLAUDE_AGENTS_DIR": self._worktree_agents_dir()}, clear=False):
            tools = load_agent_tools("sandbox-verify-engineer")

        self.assertEqual(
            tools,
            ["Read", "Grep", "Glob", "Bash"],
            f"sandbox-verify-engineer tools drift: {tools!r}",
        )

    def test_loaded_tools_exclude_write_edit_multiedit(self):
        from agent_tools_loader import load_agent_tools

        with patch.dict(os.environ, {"CLAUDE_AGENTS_DIR": self._worktree_agents_dir()}, clear=False):
            tools = load_agent_tools("sandbox-verify-engineer")

        self.assertIsNotNone(tools, "load_agent_tools returned None")
        for forbidden in ("Write", "Edit", "MultiEdit", "Agent", "Skill"):
            self.assertNotIn(
                forbidden,
                tools,
                f"forbidden tool {forbidden!r} should NOT be in allowlist",
            )


# ---------------------------------------------------------------------------
# AC3 — Skip without token: emits SANDBOX_SKIPPED + appends one JSONL line.
# ---------------------------------------------------------------------------

class AC3SkipWithoutTokenTest(unittest.TestCase):
    """AC3: With E2B_API_KEY unset, emit_skip_if_no_token returns
    verdict=SANDBOX_SKIPPED, reason=no-e2b-token, ISO-8601 timestamp;
    appends exactly one JSONL line to the skip log path.
    """

    def test_returns_verdict_and_iso_timestamp(self):
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            # Env-var hygiene per plan's Hard Constraint 3.
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                result = emit_skip_if_no_token(
                    session_id="test-session-spec-blind",
                    metrics_dir=tmp,
                )

            self.assertEqual(result["verdict"], "SANDBOX_SKIPPED")
            self.assertEqual(result["reason"], "no-e2b-token")

            # Timestamp parses as ISO-8601.
            ts = result["timestamp"]
            self.assertIsInstance(ts, str)
            # `datetime.fromisoformat` handles both naive and aware ISO-8601
            # forms. Python 3.11+ also accepts trailing 'Z' for UTC.
            try:
                datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError as exc:  # pragma: no cover
                self.fail(f"timestamp {ts!r} is not ISO-8601: {exc}")

    def test_appends_exactly_one_jsonl_line_with_reason(self):
        from sandbox_verify_skip import emit_skip_if_no_token

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                emit_skip_if_no_token(
                    session_id="test-session-spec-blind",
                    metrics_dir=tmp,
                )

            log_path = pathlib.Path(tmp) / "test-session-spec-blind" / "sandbox-verify-skips.jsonl"
            self.assertTrue(
                log_path.exists(),
                f"skip log file does not exist at {log_path}",
            )

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1, f"expected exactly one line, got {len(lines)}: {lines!r}")

            record = json.loads(lines[0])
            self.assertEqual(record["reason"], "no-e2b-token")


# ---------------------------------------------------------------------------
# AC4 — Diff algorithm: compare_pass_sets behavioural contract.
# ---------------------------------------------------------------------------

class AC4DiffAlgorithmTest(unittest.TestCase):
    """AC4: compare_pass_sets returns verdict + sorted diverging test names.

    Behavioural cases derived directly from the SKILL.md procedure:
      - empty/empty → VERIFIED, []
      - identical pass sets → VERIFIED, []
      - one test flips pass→fail → FAILED, [test_name]
      - test removed from sandbox → FAILED, [removed_name]
      - multiple divergences → FAILED, sorted alphabetically
    """

    def test_both_empty_returns_verified_and_empty_list(self):
        from sandbox_verify_diff import compare_pass_sets

        result = compare_pass_sets({}, {})
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED")
        self.assertEqual(result["diverging_tests"], [])

    def test_identical_pass_sets_returns_verified(self):
        from sandbox_verify_diff import compare_pass_sets

        result = compare_pass_sets({"t1": "pass"}, {"t1": "pass"})
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED")
        self.assertEqual(result["diverging_tests"], [])

    def test_test_flips_pass_to_fail_returns_failed_with_name(self):
        from sandbox_verify_diff import compare_pass_sets

        result = compare_pass_sets({"t1": "pass"}, {"t1": "fail"})
        self.assertEqual(result["verdict"], "SANDBOX_FAILED")
        self.assertEqual(result["diverging_tests"], ["t1"])

    def test_test_missing_from_sandbox_returns_failed_with_name(self):
        from sandbox_verify_diff import compare_pass_sets

        result = compare_pass_sets({"a": "pass", "b": "pass"}, {"a": "pass"})
        self.assertEqual(result["verdict"], "SANDBOX_FAILED")
        self.assertEqual(result["diverging_tests"], ["b"])

    def test_diverging_test_names_are_sorted_alphabetically(self):
        from sandbox_verify_diff import compare_pass_sets

        # Both "a" and "z" are in worktree pass set; neither is in sandbox.
        # Sorted order should be ["a", "z"], regardless of input dict order.
        result = compare_pass_sets({"z": "pass", "a": "pass"}, {})
        self.assertEqual(result["diverging_tests"], ["a", "z"])


# ---------------------------------------------------------------------------
# AC5 — Instinct intersection: seed loads + roles intersect agent categories.
# ---------------------------------------------------------------------------

class AC5InstinctIntersectionTest(unittest.TestCase):
    """AC5: The seed instinct loads, validates clean, and shares >=1 role
    token with the agent's instinct_categories — guaranteeing the spawn
    receives a non-empty learned-patterns block.

    Public API discovered via the orchestrator-handed signatures:
      - `parse_file(path: pathlib.Path) -> (meta_dict, body_str)` tuple.
      - `validate(meta_dict, body_str) -> None | warning_code` (None == clean).
      - `load_agent_instinct_categories(role) -> list[str]` (env: CLAUDE_AGENTS_DIR).
    """

    def _worktree_agents_dir(self):
        return str(REPO_ROOT / "agents")

    def test_seed_instinct_loads_and_validates_clean(self):
        from instinct_loader_helpers import parse_file, validate

        seed_path = REPO_ROOT / "learning" / "instincts" / "sandbox-verify-seed.md"
        meta, body = parse_file(seed_path)
        self.assertIsNotNone(meta, f"parse_file returned None meta for {seed_path}")
        self.assertTrue(body.strip(), "parse_file returned empty body")

        # validate returns None on success per plan's Hard Constraint 6.
        result = validate(meta, body)
        self.assertIsNone(
            result,
            f"seed instinct failed validation: {result!r}",
        )

    def test_seed_roles_intersect_agent_instinct_categories(self):
        from instinct_loader_helpers import parse_file
        from agent_instinct_categories_loader import load_agent_instinct_categories

        seed_path = REPO_ROOT / "learning" / "instincts" / "sandbox-verify-seed.md"
        meta, _body = parse_file(seed_path)
        seed_roles = set(meta.get("roles", []))

        with patch.dict(os.environ, {"CLAUDE_AGENTS_DIR": self._worktree_agents_dir()}, clear=False):
            agent_categories = set(load_agent_instinct_categories("sandbox-verify-engineer"))

        intersection = seed_roles & agent_categories
        self.assertGreaterEqual(
            len(intersection),
            1,
            f"seed roles {seed_roles!r} do not intersect agent categories "
            f"{agent_categories!r} — instinct injection would yield an empty "
            f"learned-patterns block",
        )


if __name__ == "__main__":
    unittest.main()
