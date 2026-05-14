"""Spec-blind validator: black-box tests authored from public-spec only.

These tests are authored by the spec-blind-validator Final-Gate teammate.
They MUST NOT read production hook/resolver source. They derive their
assertions from:

  1. The user-facing proposal file
     (protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md), which is
     the public contract for operator copy + reason enum + promotion criterion.
  2. rules/core.md Iron Law 2 (the documentation contract for the marker).
  3. agents/patch-critic.md (the documentation contract for the APPEND).
  4. The hook's BLACK-BOX executable interface
     (hooks/verification-freshness-guard.sh invoked with stdin JSON envelope).
     The hook is treated as an opaque executable; its internals are NOT read.

Catches the SWE-Bench-Pro-vs-Verified failure mode where build-time tests
codify the same misconceptions about the spec as production code does.
"""
import json
import os
import re
import subprocess
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = REPO_ROOT / "protocols" / "_proposals" / "2026-05-14-iron-law-2-freshness-hook.md"
RULES_CORE = REPO_ROOT / "rules" / "core.md"
PATCH_CRITIC_MD = REPO_ROOT / "agents" / "patch-critic.md"
HOOK = REPO_ROOT / "hooks" / "verification-freshness-guard.sh"


# ---------------------------------------------------------------------------
# Helpers (black-box only — no production source imports)
# ---------------------------------------------------------------------------

def _read(path):
    return path.read_text(encoding="utf-8")


def _run_hook_blackbox(payload, env_extra=None):
    """Invoke the hook as a black-box executable via its stdin JSON contract.

    No knowledge of the hook's internal implementation is required — this
    treats `bash <hook> < stdin_json` as the public surface the harness uses
    when registering it under settings.json PreToolUse Agent.
    """
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _session_log_path(session):
    return Path.home() / ".claude" / "metrics" / session / "freshness-guard.jsonl"


def _cleanup_session(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test 1: reason-enum self-consistency between Operator Copy table and the
# documented JSONL schema in the proposal.
#
# Public-spec invariant: the proposal's `## Operator Copy` table MUST enumerate
# the same set of `reason` values as the proposal's § Freshness Rules section
# describes. If they diverge, operators reading the proposal would see operator
# copy for a reason they cannot reach, OR a reason emitted at runtime would
# have no documented stderr/recovery action.
# ---------------------------------------------------------------------------

class TestProposalOperatorCopySelfConsistent(unittest.TestCase):
    def test_operator_copy_reasons_match_freshness_rules_reasons(self):
        text = _read(PROPOSAL)

        # Extract reasons from the Operator Copy markdown table.
        # Rows look like:  | `reason_value` | ... |
        # Skip the header divider (---) row.
        operator_section_match = re.search(
            r"##\s+Operator Copy\s*\n(.*?)(?=\n##\s|\Z)",
            text, flags=re.DOTALL)
        self.assertIsNotNone(
            operator_section_match,
            "proposal MUST contain `## Operator Copy` section (AC1.4)")
        operator_section = operator_section_match.group(1)

        operator_reasons = set()
        for line in operator_section.splitlines():
            # Match leading-pipe table row whose first cell is a backticked literal
            m = re.match(r"^\|\s*`([a-z0-9_]+)`\s*\|", line)
            if m:
                operator_reasons.add(m.group(1))

        # The Freshness Rules section enumerates the reasons emitted at runtime.
        # Extract any backticked `snake_case_word` appearing on a `reason:` line.
        rules_section_match = re.search(
            r"###\s+Freshness rules\s*\n(.*?)(?=\n##\s|\n###\s|\Z)",
            text, flags=re.DOTALL)
        self.assertIsNotNone(
            rules_section_match,
            "proposal MUST contain `### Freshness rules` section")
        rules_section = rules_section_match.group(1)
        rules_reasons = set(re.findall(r"`reason:\s*([a-z0-9_]+)`", rules_section))

        # Public-spec invariant: every reason mentioned in § Freshness Rules
        # (the runtime rule-class enum) MUST have a corresponding row in
        # Operator Copy (the operator-facing recovery contract). The reverse
        # is allowed — Operator Copy MAY enumerate additional resolver-internal
        # failure modes (e.g. `fresh` PASS path, `state_file_parse_error`,
        # `git_timeout`) that are not phrased as numbered rules in
        # § Freshness Rules. The forbidden state is a reason emitted at runtime
        # whose operator-copy row is missing — operators would have no
        # documented recovery action.
        missing_copy = rules_reasons - operator_reasons
        self.assertEqual(
            missing_copy, set(),
            f"Reasons emitted by § Freshness Rules but absent from Operator "
            f"Copy table: {missing_copy}. Every runtime-emitted reason MUST "
            f"have a documented stderr template + recovery action. "
            f"Operator-copy reasons: {sorted(operator_reasons)}; "
            f"freshness-rules reasons: {sorted(rules_reasons)}.")


# ---------------------------------------------------------------------------
# Test 2: hook is a no-op on non-gated roles (black-box stdin contract)
#
# Public-spec invariant (proposal § Proposed Solution + plan AC3.2): the hook
# runs on patch-critic / product-reviewer / pr-creation ONLY. A spawn for
# software-engineer (a build-phase role) must NOT emit any JSONL.
# ---------------------------------------------------------------------------

class TestHookNoOpOnNonGatedRole(unittest.TestCase):
    def test_software_engineer_spawn_emits_no_jsonl(self):
        session = f"spec-blind-noop-{uuid.uuid4().hex[:8]}"
        log = _session_log_path(session)
        _cleanup_session(log)
        try:
            payload = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "software-engineer"},
            }
            result = _run_hook_blackbox(payload, env_extra={
                "CLAUDE_SESSION_ID": session,
                "CLAUDE_HOOK_PROFILE": "standard",
            })
            # Black-box contract: exit 0 + no JSONL written.
            self.assertEqual(
                result.returncode, 0,
                f"hook must exit 0 on non-gated role; "
                f"stdout={result.stdout!r} stderr={result.stderr!r}")
            self.assertFalse(
                log.exists(),
                f"hook must NOT write JSONL for non-gated role; "
                f"unexpected file at {log}")
        finally:
            _cleanup_session(log)


# ---------------------------------------------------------------------------
# Test 3: rules/core.md Iron Law 2 documentation marker is present.
#
# Public-spec invariant (AC1.2): rules/core.md Iron Law 2 line must reference
# the hook path, the v2.1.141 version stamp, and the permissionDecision
# upgrade gate. This is the operator-facing breadcrumb from the iron law to
# the enforcement mechanism.
# ---------------------------------------------------------------------------

class TestIronLaw2MarkerInvariant(unittest.TestCase):
    def test_iron_law_2_line_references_hook_version_and_promotion_gate(self):
        text = _read(RULES_CORE)
        # Find the line with "NO COMPLETION CLAIMS" (Iron Law 2)
        matching_lines = [
            line for line in text.splitlines()
            if "NO COMPLETION CLAIMS" in line
        ]
        self.assertEqual(
            len(matching_lines), 1,
            "rules/core.md must contain exactly one 'NO COMPLETION CLAIMS' "
            "line (Iron Law 2)")
        iron_law_2_line = matching_lines[0]

        for required in (
            "verification-freshness-guard.sh",
            "v2.1.141",
            "permissionDecision",
        ):
            self.assertIn(
                required, iron_law_2_line,
                f"Iron Law 2 line must contain {required!r}; got "
                f"{iron_law_2_line!r}")


# ---------------------------------------------------------------------------
# Test 4: patch-critic.md APPEND invariant.
#
# Public-spec invariant (AC5.1): the Operating Discipline paragraph at the
# top of agents/patch-critic.md (a single dense paragraph including the
# "Tool-result fabrication is forbidden." sentence) must be APPENDED with a
# reference to the new hook. Both must coexist on the same paragraph (proves
# the APPEND was additive, not a replacement).
# ---------------------------------------------------------------------------

class TestPatchCriticAppendInvariant(unittest.TestCase):
    def test_tool_result_fabrication_paragraph_also_references_freshness_guard(self):
        text = _read(PATCH_CRITIC_MD)

        # The fabrication sentence sits on a paragraph (single line in markdown).
        # The append must place the hook reference ON THE SAME LINE.
        matching_lines = [
            line for line in text.splitlines()
            if "Tool-result fabrication" in line
        ]
        self.assertGreaterEqual(
            len(matching_lines), 1,
            "patch-critic.md must contain a 'Tool-result fabrication' "
            "Operating Discipline paragraph")

        # AC5.1 demands an APPEND, not a paragraph split — so the same line
        # must also reference the hook.
        same_line_with_hook = [
            line for line in matching_lines
            if "verification-freshness-guard.sh" in line
        ]
        self.assertEqual(
            len(same_line_with_hook), len(matching_lines),
            "patch-critic.md: every 'Tool-result fabrication' paragraph must "
            "also reference 'verification-freshness-guard.sh' on the SAME "
            "line (AC5.1 APPEND, not paragraph split). "
            f"Found {len(matching_lines)} fabrication line(s); "
            f"{len(same_line_with_hook)} also reference the hook.")


# ---------------------------------------------------------------------------
# Test 5: proposal § Promotion Criterion structural invariant.
#
# Public-spec invariant (AC1.3): proposal must contain `## Promotion Criterion`
# section, and the section must enumerate three numbered clauses, each
# touching one of the required gates (14-day soak / 50 pipelines /
# permissionDecision / operator review).
# ---------------------------------------------------------------------------

class TestPromotionCriterionStructure(unittest.TestCase):
    def test_promotion_criterion_section_with_three_numbered_clauses(self):
        text = _read(PROPOSAL)

        # Section presence
        section_match = re.search(
            r"##\s+Promotion Criterion\s*\n(.*?)(?=\n##\s|\Z)",
            text, flags=re.DOTALL)
        self.assertIsNotNone(
            section_match,
            "proposal MUST contain `## Promotion Criterion` heading (AC1.3)")
        section = section_match.group(1)

        # Three numbered clauses (markdown ordered list starting with `1.`, `2.`, `3.`)
        for clause_num in ("1.", "2.", "3."):
            self.assertIn(
                clause_num, section,
                f"Promotion Criterion section must contain numbered clause "
                f"`{clause_num}`")

        # Required substantive substrings — these are the gates the operator
        # is contractually told to verify before flipping the hook to exit-2.
        # The proposal phrases them as "14 days", "50 pipelines",
        # "permissionDecision", and "Operator review".
        required_terms = ["14 days", "50 pipelines", "permissionDecision",
                          "Operator review"]
        missing = [t for t in required_terms if t not in section]
        self.assertEqual(
            missing, [],
            f"Promotion Criterion section missing required term(s): {missing}. "
            f"Each clause must be inspectable by an operator without ambiguity.")


if __name__ == "__main__":
    unittest.main()
