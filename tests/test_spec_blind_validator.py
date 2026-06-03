"""Spec-blind validator tests — covers AC1-4, AC8, AC9, AC12-14, AC18.

Bats tests cover the runtime hooks (AC5-7, AC10-11, AC15-bats, AC17).
This file covers the static structure: catalog, agent, skill, settings.json
registration, dispatch wiring, recursion-guard helper, and PR-narrative
rendering for the SPEC_BLIND_INSUFFICIENT_SURFACE skip case.
"""
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

from tests._helpers.settings_hook import effective_command_line

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


class VerdictCatalogContainsFourSpecBlindRows(unittest.TestCase):
    """AC1 — four verdicts present with correct routing for SPEC_BLIND_BLOCKED."""

    def test_verdict_catalog_contains_four_spec_blind_rows_with_blocked_routing(self):
        catalog = _read("protocols/verdict-catalog.md")
        self.assertIn("`SPEC_BLIND_VALIDATED`", catalog)
        self.assertIn("`SPEC_BLIND_FAILED`", catalog)
        self.assertIn("`SPEC_BLIND_INSUFFICIENT_SURFACE`", catalog)
        self.assertIn("`SPEC_BLIND_BLOCKED`", catalog)
        # SPEC_BLIND_BLOCKED row must declare HALT routing, not auto-advance, not fix-engineer.
        # Find the line containing SPEC_BLIND_BLOCKED and inspect it.
        blocked_line = next(
            (ln for ln in catalog.splitlines() if "`SPEC_BLIND_BLOCKED`" in ln),
            "",
        )
        self.assertTrue(blocked_line, "SPEC_BLIND_BLOCKED row not found")
        self.assertIn("HALT", blocked_line)
        # MUST explicitly state that fix-engineer is NOT the routing — phrasing should
        # negate fix-engineer routing (e.g. "do NOT route to fix-engineer", "no fix-engineer dispatch").
        self.assertRegex(
            blocked_line,
            r"(?i)(?:do NOT|never|no)\s+(?:route to |dispatch |spawn |send to )?fix-engineer",
            "SPEC_BLIND_BLOCKED routing must explicitly negate fix-engineer dispatch",
        )


class AgentFrontmatterMatchesSpec(unittest.TestCase):
    """AC2 — agent file declares expected fields and prose."""

    def setUp(self):
        self.path = REPO_ROOT / "agents" / "spec-blind-validator.md"
        self.assertTrue(self.path.exists(), "agents/spec-blind-validator.md missing")
        self.text = self.path.read_text()

    def test_tools_list_contains_required_five_and_excludes_edit(self):
        # SEC-MED-3 — Edit dropped (validator only authors NEW test files via
        # Write; Edit was over-broad attack surface).
        for tool in ("Read", "Write", "Bash", "Grep", "Glob"):
            self.assertIsNotNone(
                re.search(rf"^\s*-\s*{tool}\s*$", self.text, re.MULTILINE),
                f"agent tools list missing: {tool}")
        self.assertIsNone(
            re.search(r"^\s*-\s*Edit\s*$", self.text, re.MULTILINE),
            "agent tools list MUST NOT include Edit (SEC-MED-3)")

    def test_disallowed_tools_present(self):
        for tool in ("Agent", "Skill", "MultiEdit"):
            self.assertIsNotNone(
                re.search(rf"^\s*-\s*{tool}\s*$", self.text, re.MULTILINE),
                f"agent disallowedTools missing: {tool}")

    def test_model_and_executor_advisor(self):
        self.assertIsNotNone(re.search(r"^model:\s*sonnet\s*$", self.text, re.MULTILINE), "model: sonnet missing")
        self.assertIsNotNone(re.search(r"^executor:\s*claude-sonnet-4-6\s*$", self.text, re.MULTILINE), "executor missing")
        self.assertIsNotNone(re.search(r"^advisor:\s*claude-opus-4-7\s*$", self.text, re.MULTILINE), "advisor missing")

    def test_instinct_categories_includes_qa_and_self(self):
        self.assertIsNotNone(re.search(r"^\s*-\s*qa-engineer\s*$", self.text, re.MULTILINE), "qa-engineer missing from instinct_categories")
        self.assertIsNotNone(re.search(r"^\s*-\s*spec-blind-validator\s*$", self.text, re.MULTILINE), "spec-blind-validator missing from instinct_categories")

    def test_max_turns_60(self):
        self.assertIsNotNone(re.search(r"^maxTurns:\s*60\s*$", self.text, re.MULTILINE), "maxTurns: 60 missing")

    def test_blind_prose_present(self):
        # Case-insensitive — leading capitalisation may vary mid-sentence vs sentence-start.
        self.assertIsNotNone(re.search(r"you do NOT see implementation source", self.text, re.IGNORECASE),
                             "agent prose missing 'you do NOT see implementation source'")
        self.assertIn("Read/Bash content-leak shapes are blocked", self.text)


class SkillFrontmatterAndBodyComplete(unittest.TestCase):
    """AC3 — skill declares 4 verdicts, agent, finite test-runner ladder, recursion guard, future work, fix-engineer constraint."""

    def setUp(self):
        self.path = REPO_ROOT / "skills" / "spec-blind-validate" / "SKILL.md"
        self.assertTrue(self.path.exists(), "skills/spec-blind-validate/SKILL.md missing")
        self.text = self.path.read_text()

    def test_verdict_field_lists_four(self):
        m = re.search(
            r"^verdict:\s*SPEC_BLIND_VALIDATED\|SPEC_BLIND_FAILED\|SPEC_BLIND_INSUFFICIENT_SURFACE\|SPEC_BLIND_BLOCKED\s*$",
            self.text, re.MULTILINE)
        self.assertIsNotNone(m, "skill verdict frontmatter line missing or malformed")

    def test_agent_declared(self):
        self.assertIsNotNone(
            re.search(r"^agent:\s*spec-blind-validator\s*$", self.text, re.MULTILINE),
            "skill must declare 'agent: spec-blind-validator'")

    def test_seven_runner_ladder(self):
        for runner in (
            "npm test",
            "pnpm test",
            "yarn test",
            "bundle exec rspec",
            "pytest",
            "cargo test",
            "go test",
        ):
            self.assertIn(runner, self.text, f"runner missing from § Process: {runner}")

    def test_recursion_guard_section(self):
        self.assertIn("## Recursion Guard", self.text)

    def test_future_work_section_names_v2_allowlist(self):
        self.assertIn("## Future Work", self.text)
        # V2 allowlist contents should be enumerated
        for entry in ("protocols/", "agents/", "skills/", "orchestrator/"):
            self.assertIn(entry, self.text, f"V2 allowlist entry missing: {entry}")

    def test_fix_engineer_constraint_section(self):
        self.assertIn("## Fix-Engineer Constraint", self.text)
        # Code-fix-only on FAILED, must not mutate ACs
        self.assertRegex(self.text, r"code-fix-only", re.IGNORECASE)
        self.assertRegex(self.text, r"MUST NOT mutate ACs|must not mutate the AC", re.IGNORECASE)


class ClaudeMdSkillDirectoryListsSpecBlindValidate(unittest.TestCase):
    """AC4 — CLAUDE.md skill row exists with all four verdicts and key descriptors."""

    def test_claude_md_skill_directory_lists_spec_blind_validate(self):
        text = _read("CLAUDE.md")
        # Find a line that is the skill row
        rows = [ln for ln in text.splitlines() if "`/spec-blind-validate`" in ln]
        self.assertTrue(rows, "CLAUDE.md missing /spec-blind-validate skill row")
        row = rows[0]
        for verdict in (
            "SPEC_BLIND_VALIDATED",
            "SPEC_BLIND_FAILED",
            "SPEC_BLIND_INSUFFICIENT_SURFACE",
            "SPEC_BLIND_BLOCKED",
        ):
            self.assertIn(verdict, row)
        # Description must call out Final Gate, spec-blind, and "ACs only, no source"
        self.assertIn("Final Gate", row)
        self.assertIn("spec-blind", row)
        self.assertIn("ACs only, no source", row)


class SettingsJsonRegistersThreeGuardsWithPortablePath(unittest.TestCase):
    """AC8 — three hook commands appear in settings.json under the right matchers, all using portable path."""

    def setUp(self):
        self.settings = json.loads((REPO_ROOT / "settings.json").read_text())
        self.pre_blocks = self.settings["hooks"]["PreToolUse"]

    def _commands_for_matcher(self, matcher: str):
        out = []
        for blk in self.pre_blocks:
            if blk.get("matcher") == matcher:
                for h in blk.get("hooks", []):
                    out.append(effective_command_line(h))
        return out

    def test_read_grep_glob_matcher_registers_read_guard(self):
        cmds = self._commands_for_matcher("Read|Grep|Glob")
        joined = "\n".join(cmds)
        self.assertIn("spec-blind-read-guard.sh", joined)
        self.assertIn("${CLAUDE_CONFIG_DIR:-$HOME/.claude}", joined)

    def test_write_edit_matcher_registers_write_guard(self):
        # CR-MED-5: write-guard registered under per-tool matchers (Write
        # AND Edit), aligning with pre-existing settings.json convention
        # (no other hook uses the disjunction "Write|Edit"). After SEC-MED-3
        # dropped Edit from the agent's tools, the Edit registration is a
        # no-op for spec-blind but is harmless and preserves convention.
        write_cmds = self._commands_for_matcher("Write")
        self.assertTrue(
            any("spec-blind-write-guard.sh" in c for c in write_cmds),
            "spec-blind-write-guard.sh missing from Write matcher",
        )
        edit_cmds = self._commands_for_matcher("Edit")
        self.assertTrue(
            any("spec-blind-write-guard.sh" in c for c in edit_cmds),
            "spec-blind-write-guard.sh missing from Edit matcher",
        )
        # Both registrations use the portable path.
        joined = "\n".join(write_cmds + edit_cmds)
        self.assertIn("${CLAUDE_CONFIG_DIR:-$HOME/.claude}", joined)

    def test_bash_matcher_registers_bash_guard(self):
        cmds = self._commands_for_matcher("Bash")
        joined = "\n".join(cmds)
        self.assertIn("spec-blind-bash-guard.sh", joined)
        self.assertIn("${CLAUDE_CONFIG_DIR:-$HOME/.claude}", joined)


class CatalogSkillParityRoundTrip(unittest.TestCase):
    """AC9 — every catalog SPEC_BLIND_* verdict appears in skill, and vice versa."""

    def test_catalog_skill_parity_round_trip(self):
        catalog = _read("protocols/verdict-catalog.md")
        skill = _read("skills/spec-blind-validate/SKILL.md")
        catalog_verdicts = set(re.findall(r"`(SPEC_BLIND_[A-Z_]+)`", catalog))
        skill_verdicts = set(re.findall(r"SPEC_BLIND_[A-Z_]+", skill))
        # Forward: catalog ⊆ skill
        self.assertTrue(catalog_verdicts.issubset(skill_verdicts),
                        f"catalog verdicts not in skill: {catalog_verdicts - skill_verdicts}")
        # Reverse: skill ⊆ catalog
        self.assertTrue(skill_verdicts.issubset(catalog_verdicts),
                        f"skill verdicts not in catalog: {skill_verdicts - catalog_verdicts}")
        self.assertEqual(catalog_verdicts, {
            "SPEC_BLIND_VALIDATED",
            "SPEC_BLIND_FAILED",
            "SPEC_BLIND_INSUFFICIENT_SURFACE",
            "SPEC_BLIND_BLOCKED",
        })


class ParallelDispatchProtocolListsSpecBlindInFinalGateTeam(unittest.TestCase):
    """AC12 — Final Gate Team table contains spec-blind-validator row + 'All five' narrative."""

    def test_final_gate_table_contains_spec_blind_row(self):
        text = _read("protocols/parallel-dispatch-protocol.md")
        # Look for spec-blind-validator row + skill + verdict
        self.assertIn("spec-blind-validator", text)
        self.assertIn("/spec-blind-validate", text)
        self.assertIn("SPEC_BLIND_VALIDATED", text)
        # Narrative was "All four assess..." — must be updated to "All five"
        self.assertIn("All five assess the same final state independently.", text)


class OrchestratorDispatchDetailsIncludesSpecBlindAgentBlock(unittest.TestCase):
    """AC13 — orchestrator dispatch contains 5th Agent block, isolation worktree, prompt hands ACs not diff."""

    def test_orchestrator_dispatch_details_includes_spec_blind_agent_block(self):
        text = _read("orchestrator/parallel-dispatch-details.md")
        # 5th Agent block within Final Gate Phase Dispatch must mention spec-blind-validator
        self.assertIn("spec-blind-validator", text)
        # Isolation: worktree
        self.assertRegex(text, r"isolation:\s*\"worktree\"")
        # Find a window of text near a spec-blind-validator subagent block
        # and assert that the prompt includes "AC list" and does NOT include
        # "git diff" within that window.
        # We approximate: find the block that contains spec-blind-validator and "Read ~/.claude/agents/spec-blind-validator.md"
        idx = text.find("spec-blind-validator")
        self.assertNotEqual(idx, -1)
        # Block window — take 800 chars around the agent block
        block_start = max(0, text.rfind("Agent({", 0, idx))
        block_end = text.find("})", idx)
        if block_end == -1:
            block_end = idx + 1500
        block = text[block_start:block_end + 2]
        self.assertIn("AC", block, "spec-blind-validator block must mention AC list in prompt")
        self.assertNotIn("git diff main...HEAD", block,
                         "spec-blind-validator prompt MUST NOT include git diff (it is contract-blind)")


class RecursionGuardWiredAndLogicCorrect(unittest.TestCase):
    """AC14 — SKILL invokes recursion helper BEFORE any read; helper returns SPEC_BLIND_INSUFFICIENT_SURFACE for harness cwd."""

    def setUp(self):
        self.skill_text = _read("skills/spec-blind-validate/SKILL.md")

    def test_helper_invoked_before_any_read_step(self):
        # Find § Process block; the recursion-guard STEP (numbered ordered list item)
        # must precede any "Read inputs"/"Read public surface" STEP.
        # Both intra-line and block-line ordering are tolerated, but the recursion
        # step's bullet number MUST be lower than the first Read-step bullet number.
        lines = self.skill_text.splitlines()
        process_idx = None
        for i, ln in enumerate(lines):
            if ln.strip().startswith("## Process"):
                process_idx = i
                break
        self.assertIsNotNone(process_idx, "SKILL § Process section missing")

        # Walk numbered steps "<n>. **..." and capture (step_number, line_idx, text)
        step_re = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*")
        steps = []
        for i in range(process_idx + 1, len(lines)):
            if lines[i].startswith("## ") and i != process_idx:
                break
            m = step_re.match(lines[i])
            if m:
                steps.append((int(m.group(1)), i, m.group(2)))

        self.assertGreaterEqual(len(steps), 2, "§ Process needs at least two numbered steps")

        recursion_step = next((s for s in steps if "recursion" in s[2].lower()), None)
        # First Read-step is the lowest-numbered step whose title STARTS with
        # "Read " (so "Read inputs" / "Read public surface" match, but
        # "Recursion-guard precheck (BEFORE any Read)" — which contains "Read"
        # only as a back-reference — does NOT).
        read_steps = [s for s in steps if s[2].startswith("Read ")]

        self.assertIsNotNone(recursion_step, "no recursion-guard step found in § Process")
        self.assertTrue(read_steps, "no Read-prefixed step found in § Process")

        first_read_step = min(read_steps, key=lambda s: s[0])
        self.assertLess(recursion_step[0], first_read_step[0],
                        f"recursion-guard step (#{recursion_step[0]}) must precede first Read step (#{first_read_step[0]})")

    def test_helper_logic_returns_insufficient_for_harness_cwd(self):
        # Helper lives in hooks/_lib/spec-blind-recursion.sh and exposes
        # `is_harness_internal_cwd <cwd>` — exit 0 when harness, 1 otherwise.
        helper = REPO_ROOT / "hooks" / "_lib" / "spec-blind-recursion.sh"
        self.assertTrue(helper.exists(), "hooks/_lib/spec-blind-recursion.sh missing")
        # Source the helper and invoke against this very repo (HARNESS itself)
        # The harness REPO_ROOT contains rules/core.md and is the CLAUDE_CONFIG_DIR.
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
        result = subprocess.run(
            ["bash", "-c", f"source '{helper}' && is_harness_internal_cwd '{REPO_ROOT}' && echo HARNESS || echo NOT"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.stdout.strip(), "HARNESS",
                         f"helper failed to detect harness cwd. stderr: {result.stderr}")

    def test_helper_logic_returns_pass_for_non_harness_cwd(self):
        helper = REPO_ROOT / "hooks" / "_lib" / "spec-blind-recursion.sh"
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
        result = subprocess.run(
            ["bash", "-c", f"source '{helper}' && is_harness_internal_cwd '/tmp' && echo HARNESS || echo NOT"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.stdout.strip(), "NOT")

    def test_helper_returns_not_when_core_md_absent(self):
        # Mutation killer: if the helper drops the rules/core.md existence check,
        # any cwd whose realpath equals CLAUDE_CONFIG_DIR realpath would falsely
        # match. Point CLAUDE_CONFIG_DIR at a directory WITHOUT rules/core.md.
        helper = REPO_ROOT / "hooks" / "_lib" / "spec-blind-recursion.sh"
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # No rules/core.md in tmp; cwd = tmp
            env = os.environ.copy()
            env["CLAUDE_CONFIG_DIR"] = tmp
            result = subprocess.run(
                ["bash", "-c", f"source '{helper}' && is_harness_internal_cwd '{tmp}' && echo HARNESS || echo NOT"],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.stdout.strip(), "NOT",
                             "helper must NOT match when rules/core.md is absent under CLAUDE_CONFIG_DIR")

    def test_helper_returns_not_when_cwd_outside_repo(self):
        # Mutation killer: if the helper drops the realpath comparison, any cwd
        # would match as long as core.md exists. Pass a non-git path.
        helper = REPO_ROOT / "hooks" / "_lib" / "spec-blind-recursion.sh"
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
        # /private/tmp is not a git repo (or its top-level differs from REPO_ROOT)
        result = subprocess.run(
            ["bash", "-c", f"source '{helper}' && is_harness_internal_cwd '/private/tmp' && echo HARNESS || echo NOT"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.stdout.strip(), "NOT")


class FinalGateSummaryRendersSkippedForInsufficientSurface(unittest.TestCase):
    """AC18 — Final Gate summary renders the skip line; PR narrative includes the one-liner."""

    def test_orchestrator_emits_skipped_summary_line(self):
        text = _read("orchestrator/parallel-dispatch-details.md")
        self.assertIn("spec-blind: SKIPPED (no public surface)", text)

    def test_pr_creation_includes_spec_blind_section(self):
        text = _read("skills/pr-creation/SKILL.md")
        self.assertIn("## Spec-Blind Validation", text)
        self.assertIn("no public-surface artifacts found in this repo", text)
        self.assertIn("V2 harness-aware path", text)


if __name__ == "__main__":
    unittest.main()
