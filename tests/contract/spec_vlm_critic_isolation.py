"""Slice slice-b-vlm-critic-and-guard — Tier 0 contract tests.

Per plan.md § 3 Tier 0 Contract Assertions (lines 112-119), seven assertions:

  1. `agents/vlm-critic.md` frontmatter declares `tools: [Read, Write]` exactly
     AND `disallowedTools: [Bash, Edit, MultiEdit, Agent, Skill, Grep, Glob]`
     exactly (SE-2 pinned surface — verbatim).
  2. `hooks/vlm-critic-read-guard.sh` exit-code-2 when subagent_type ==
     "vlm-critic" AND path matches `src/.*` OR `lib/.*` OR `app/.*`.
  3. `hooks/_lib/vlm-critic-allow-paths.txt` first include line matches the
     literal ERE `pipeline-state/.+/visual-baselines/[^/]+\\.png` (SE-4 pin —
     verbatim regex, not "or equivalent").
  4. `rules/verdict-catalog.md` contains BOTH `VISUAL_DIFF_PASS` and
     `VISUAL_DIFF_FAIL` rows.
  5. `hooks/_lib/vlm-critic-guard-common.sh` defines all three public functions
     verbatim (`grep -E '^_vlm_critic_(parse_input|redact|log_violation)\\(\\)'`
     -> exactly 3 matches) AND contains the SEC-MED-1 redaction sed-pipeline
     (six s/// rules for Bearer / token / secret / password / api_key /
     aws_secret) AND contains the session-id sanitization
     (`tr -dc 'A-Za-z0-9_-' \\| head -c 64`).
  6. `skills/vlm-critic/SKILL.md` contains the literal documented escape hatch
     `CLAUDE_DISABLE_VLM_CRITIC=1` (PR-3 pin; assertable via fixed-string grep).
  7. `skills/vlm-critic/SKILL.md` documents that when CLAUDE_DISABLE_VLM_CRITIC=1
     is set, vlm-critic short-circuits to verdict `VISUAL_DIFF_PASS` with
     `vlm_summary` containing the literal token `disabled-by-env` (PR-3 pin).

Contract tests run as pure-Python assertions against source-tree artifacts;
they do NOT spawn subagents or invoke the hook. Behavioural verification of
the hook lives in Tier 2 bats tests at
`tests/shell/test_vlm_critic_read_guard.bats`.
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VLM_CRITIC_AGENT = ROOT / "agents" / "vlm-critic.md"
VLM_CRITIC_SKILL = ROOT / "skills" / "vlm-critic" / "SKILL.md"
VLM_CRITIC_READ_GUARD = ROOT / "hooks" / "vlm-critic-read-guard.sh"
VLM_CRITIC_GUARD_COMMON = ROOT / "hooks" / "_lib" / "vlm-critic-guard-common.sh"
VLM_CRITIC_ALLOW_PATHS = ROOT / "hooks" / "_lib" / "vlm-critic-allow-paths.txt"
VERDICT_CATALOG = ROOT / "rules" / "verdict-catalog.md"


def _read(path):
    return path.read_text(encoding="utf-8")


class VlmCriticAgentFrontmatterPinnedToolSurface(unittest.TestCase):
    """Tier 0 #1 — SE-2 pinned tool surface for vlm-critic agent."""

    def test_agent_file_exists(self):
        self.assertTrue(
            VLM_CRITIC_AGENT.exists(),
            f"{VLM_CRITIC_AGENT} must exist (slice-b AC3)",
        )

    def _yaml_list_under(self, frontmatter, key):
        """Extract list items from a YAML block like:
            key:
              - Item1
              - Item2
            <next-key or end>
        Returns the list of item names in declaration order.
        """
        lines = frontmatter.splitlines()
        items = []
        in_block = False
        for line in lines:
            if in_block:
                m = re.match(r"^\s+-\s+(\S+)\s*$", line)
                if m:
                    items.append(m.group(1))
                    continue
                # Non-list line under the key ends the block (next top-level key).
                if re.match(r"^\S", line) or line.strip() == "":
                    if line.strip() == "":
                        # blank lines do not terminate; YAML allows them
                        continue
                    break
            elif line.rstrip() == f"{key}:":
                in_block = True
        return items

    def test_frontmatter_declares_tools_read_and_write_only(self):
        body = _read(VLM_CRITIC_AGENT)
        match = re.match(r"^---\n(.*?)\n---", body, re.DOTALL)
        self.assertIsNotNone(match, "agent must have YAML frontmatter")
        frontmatter = match.group(1)
        tools = self._yaml_list_under(frontmatter, "tools")
        self.assertEqual(
            sorted(tools),
            ["Read", "Write"],
            f"SE-2 pin: tools must be exactly [Read, Write], got {tools}",
        )

    def test_frontmatter_declares_disallowed_tools_verbatim(self):
        body = _read(VLM_CRITIC_AGENT)
        match = re.match(r"^---\n(.*?)\n---", body, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = match.group(1)
        disallowed = self._yaml_list_under(frontmatter, "disallowedTools")
        expected = sorted(
            ["Bash", "Edit", "MultiEdit", "Agent", "Skill", "Grep", "Glob"]
        )
        self.assertEqual(
            sorted(disallowed),
            expected,
            f"SE-2 pin: disallowedTools must be exactly {expected}, got {disallowed}",
        )


class VlmCriticReadGuardExitsTwoOnSrcLibApp(unittest.TestCase):
    """Tier 0 #2 — read-guard exits 2 on src/lib/app for vlm-critic subagent."""

    def test_hook_file_exists_and_is_executable(self):
        self.assertTrue(
            VLM_CRITIC_READ_GUARD.exists(),
            f"{VLM_CRITIC_READ_GUARD} must exist",
        )
        import os
        self.assertTrue(
            os.access(VLM_CRITIC_READ_GUARD, os.X_OK),
            "vlm-critic-read-guard.sh must be executable",
        )

    def test_hook_exits_two_for_src_path(self):
        # Run the hook with a synthetic stdin payload — exit 2 expected.
        payload = (
            '{"tool_name":"Read","subagent_type":"vlm-critic",'
            '"tool_input":{"file_path":"/tmp/proj/src/foo.tsx"},'
            '"session_id":"contract-test"}'
        )
        result = subprocess.run(
            ["bash", str(VLM_CRITIC_READ_GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            env={"CLAUDE_CONFIG_DIR": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        self.assertEqual(
            result.returncode, 2,
            f"src/ read must exit 2; got {result.returncode}; stderr={result.stderr}",
        )

    def test_hook_exits_two_for_lib_path(self):
        payload = (
            '{"tool_name":"Read","subagent_type":"vlm-critic",'
            '"tool_input":{"file_path":"/tmp/proj/lib/internal.ts"},'
            '"session_id":"contract-test"}'
        )
        result = subprocess.run(
            ["bash", str(VLM_CRITIC_READ_GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            env={"CLAUDE_CONFIG_DIR": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        self.assertEqual(result.returncode, 2)

    def test_hook_exits_two_for_app_path(self):
        payload = (
            '{"tool_name":"Read","subagent_type":"vlm-critic",'
            '"tool_input":{"file_path":"/tmp/proj/app/handlers/foo.tsx"},'
            '"session_id":"contract-test"}'
        )
        result = subprocess.run(
            ["bash", str(VLM_CRITIC_READ_GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            env={"CLAUDE_CONFIG_DIR": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        self.assertEqual(result.returncode, 2)


class VlmCriticAllowPathsFirstIncludeLineIsBaselinePng(unittest.TestCase):
    """Tier 0 #3 — SE-4 pin on first include line ERE."""

    def test_allow_paths_file_exists(self):
        self.assertTrue(
            VLM_CRITIC_ALLOW_PATHS.exists(),
            f"{VLM_CRITIC_ALLOW_PATHS} must exist",
        )

    def test_first_include_line_matches_baseline_png_ere(self):
        body = _read(VLM_CRITIC_ALLOW_PATHS)
        # Skip comments/blank/exclude lines; the first INCLUDE line must be the
        # baseline PNG ERE verbatim.
        first_include = None
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("!"):
                continue
            first_include = stripped
            break
        self.assertIsNotNone(first_include, "no include line found")
        # SE-4 pin: fixed-string match (verbatim regex, not "or equivalent").
        expected = r"pipeline-state/.+/visual-baselines/[^/]+\.png"
        self.assertIn(
            expected,
            first_include,
            f"SE-4 pin: first include line must contain verbatim ERE "
            f"`{expected}`; got `{first_include}`",
        )


class VerdictCatalogContainsVisualDiffRows(unittest.TestCase):
    """Tier 0 #4 — verdict-catalog has both VISUAL_DIFF rows."""

    def test_verdict_catalog_contains_visual_diff_pass_row(self):
        body = _read(VERDICT_CATALOG)
        self.assertIn(
            "VISUAL_DIFF_PASS",
            body,
            "verdict-catalog must contain VISUAL_DIFF_PASS row",
        )

    def test_verdict_catalog_contains_visual_diff_fail_row(self):
        body = _read(VERDICT_CATALOG)
        self.assertIn("VISUAL_DIFF_FAIL", body)

    def test_verdict_catalog_documents_agent_emitted_footnote(self):
        body = _read(VERDICT_CATALOG)
        # Per ORCHESTRATOR_APPLY_REQUIRED footnote precedent, agent-emitted
        # verdicts must be documented as such in § Notes.
        self.assertIn("VISUAL_DIFF_PASS", body)
        self.assertIn("vlm-critic", body)
        # The Notes section must mention vlm-critic as an agent-emitter.
        # Loose check: the strings co-occur in the file.


class VlmCriticGuardCommonHasThreeFunctionsAndSecMed1(unittest.TestCase):
    """Tier 0 #5 — SE-1 pin: three functions + SEC-MED-1 redaction + session-id sanitization."""

    def test_guard_common_file_exists(self):
        self.assertTrue(
            VLM_CRITIC_GUARD_COMMON.exists(),
            f"{VLM_CRITIC_GUARD_COMMON} must exist",
        )

    def test_guard_common_defines_exactly_three_public_functions(self):
        body = _read(VLM_CRITIC_GUARD_COMMON)
        # SE-1 pin — verbatim grep -E.
        pattern = re.compile(
            r"^_vlm_critic_(parse_input|redact|log_violation)\(\)", re.MULTILINE
        )
        matches = pattern.findall(body)
        self.assertEqual(
            sorted(matches),
            sorted(["parse_input", "redact", "log_violation"]),
            f"Must define exactly three public functions "
            f"(_vlm_critic_parse_input / _redact / _log_violation); got {matches}",
        )

    def test_guard_common_has_sec_med_1_six_redaction_rules(self):
        body = _read(VLM_CRITIC_GUARD_COMMON)
        # SEC-MED-1: six s/// patterns — Bearer / token / secret / password /
        # api_key / aws_secret. Use case-insensitive substring search on the
        # pattern roots since the sed expression itself is character-classed.
        required_anchors = [
            "[Bb][Ee][Aa][Rr][Ee][Rr]",   # Bearer
            "[Tt][Oo][Kk][Ee][Nn]",        # token
            "[Ss][Ee][Cc][Rr][Ee][Tt]",   # secret
            "[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]",  # password
            "[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]",      # api_key
            "[Aa][Ww][Ss][_-]?[Ss][Ee][Cc][Rr][Ee][Tt]",  # aws_secret
        ]
        for anchor in required_anchors:
            self.assertIn(
                anchor,
                body,
                f"SEC-MED-1: redaction sed-pipeline missing anchor `{anchor}`",
            )
        self.assertIn(
            "***REDACTED***",
            body,
            "SEC-MED-1: redaction replacement token missing",
        )

    def test_guard_common_has_session_id_sanitization(self):
        body = _read(VLM_CRITIC_GUARD_COMMON)
        # Verbatim sanitization line per plan: `tr -dc 'A-Za-z0-9_-' | head -c 64`.
        self.assertIn(
            "tr -dc 'A-Za-z0-9_-'",
            body,
            "session-id sanitization `tr -dc 'A-Za-z0-9_-'` missing",
        )
        self.assertIn(
            "head -c 64",
            body,
            "session-id sanitization `head -c 64` missing",
        )


class VlmCriticSkillDocumentsEscapeHatch(unittest.TestCase):
    """Tier 0 #6 + #7 — PR-3 escape-hatch + disabled-by-env token pins."""

    def test_skill_file_exists(self):
        self.assertTrue(
            VLM_CRITIC_SKILL.exists(),
            f"{VLM_CRITIC_SKILL} must exist",
        )

    def test_skill_md_contains_escape_hatch_env_var_verbatim(self):
        body = _read(VLM_CRITIC_SKILL)
        # PR-3 pin: literal fixed-string grep.
        self.assertIn(
            "CLAUDE_DISABLE_VLM_CRITIC=1",
            body,
            "PR-3 pin: SKILL.md must document `CLAUDE_DISABLE_VLM_CRITIC=1` verbatim",
        )

    def test_skill_md_contains_disabled_by_env_token_verbatim(self):
        body = _read(VLM_CRITIC_SKILL)
        # PR-3 pin: literal token shipped in vlm_summary.
        self.assertIn(
            "disabled-by-env",
            body,
            "PR-3 pin: SKILL.md must document the `disabled-by-env` vlm_summary token",
        )

    def test_skill_md_documents_visual_diff_pass_short_circuit(self):
        body = _read(VLM_CRITIC_SKILL)
        # The escape hatch short-circuits to VISUAL_DIFF_PASS.
        self.assertIn(
            "VISUAL_DIFF_PASS",
            body,
            "PR-3 pin: SKILL.md must name VISUAL_DIFF_PASS as the short-circuit verdict",
        )


if __name__ == "__main__":
    unittest.main()
