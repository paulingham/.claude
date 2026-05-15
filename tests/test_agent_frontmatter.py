"""Every agent file must declare both `executor:` and `advisor:` fields.

Locks in the executor/advisor frontmatter contract introduced for the
Sonnet-executor + Opus-advisor pairing pattern. `advisor: none` (a string)
is acceptable when an advisor is intentionally not configured.

Slice-C additions: model-demotion contract for planning-agent and
architect-context-recon (Haiku flips, Model Note prose, fixture, baseline
cost report stub).
"""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
EXCLUDED_SUBDIRS = {"dynamic", "archive"}


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _discover_agent_files() -> list:
    files = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if any(part in EXCLUDED_SUBDIRS for part in path.relative_to(AGENTS_DIR).parts):
            continue
        files.append(path)
    return files


def _is_valid_executor(value) -> bool:
    return isinstance(value, str) and value.startswith("claude-")


def _is_valid_advisor(value) -> bool:
    if value == "none":
        return True
    return isinstance(value, str) and value.startswith("claude-")


class EveryAgentDeclaresExecutorAndAdvisor(unittest.TestCase):
    def test_executor_present_and_valid(self):
        for path in _discover_agent_files():
            fm = _parse_frontmatter(path)
            value = fm.get("executor")
            self.assertTrue(
                _is_valid_executor(value),
                f"{path.name}: 'executor' missing or invalid (got {value!r}); "
                f"expected a string starting with 'claude-'",
            )

    def test_advisor_present_and_valid(self):
        for path in _discover_agent_files():
            fm = _parse_frontmatter(path)
            self.assertIn(
                "advisor", fm,
                f"{path.name}: 'advisor' field missing from frontmatter",
            )
            value = fm["advisor"]
            self.assertTrue(
                _is_valid_advisor(value),
                f"{path.name}: 'advisor' invalid (got {value!r}); "
                f"expected 'none' or a string starting with 'claude-'",
            )


PLANNING_AGENT = REPO_ROOT / "agents" / "planning-agent.md"
RECON_AGENT = REPO_ROOT / "agents" / "architect-context-recon.md"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "recon_code_archaeology_haiku_replay.md"
BASELINE_REPORT = REPO_ROOT / "metrics" / "reports" / "2026-05-baseline-cost.md"
CITATION_RE = re.compile(r"[a-z/_-]+\.(py|md|sh|json):\d+")


class SliceCModelDemotions(unittest.TestCase):
    def test_planning_agent_is_haiku(self):
        fm = _parse_frontmatter(PLANNING_AGENT)
        self.assertEqual(fm.get("model"), "haiku")
        self.assertEqual(fm.get("executor"), "claude-haiku-4-5-20251001")

    def test_planning_agent_model_note_mentions_haiku_and_drops_sonnet(self):
        body = PLANNING_AGENT.read_text()
        self.assertIn("Haiku 4.5 only", body)
        # Broad regex catches any stale "Sonnet 4.6" reference anywhere in the
        # body (role description, model note, prose) — not just the literal
        # "Sonnet 4.6 only" string. The advisor-rationale frontmatter comment
        # is permitted to reference the demotion history ("Demoted from Sonnet
        # to Haiku") because it lives above the body in frontmatter.
        self.assertIsNone(
            re.search(r"Sonnet\s*4\.6", body),
            "planning-agent.md body must not reference Sonnet 4.6 (stale "
            "after slice-C demotion to Haiku 4.5)",
        )

    def test_architect_context_recon_is_haiku(self):
        fm = _parse_frontmatter(RECON_AGENT)
        self.assertEqual(fm.get("model"), "haiku")
        self.assertEqual(fm.get("executor"), "claude-haiku-4-5-20251001")

    def test_recon_code_archaeology_fixture_exists_and_has_citations(self):
        self.assertTrue(FIXTURE_PATH.exists(), f"missing fixture: {FIXTURE_PATH}")
        text = FIXTURE_PATH.read_text()
        matches = [line for line in text.splitlines() if CITATION_RE.search(line)]
        self.assertGreaterEqual(
            len(matches), 3,
            f"fixture must contain >=3 file:line citations, found {len(matches)}",
        )

    def test_baseline_cost_report_exists(self):
        self.assertTrue(BASELINE_REPORT.exists(), f"missing report: {BASELINE_REPORT}")
        body = BASELINE_REPORT.read_text()
        for token in ("planning-agent", "code-reviewer", "CB<6"):
            self.assertIn(token, body)


# ---------------------------------------------------------------------------
# Slice E2 (model-demotion-pass-2026-05): hard-lock invariant tests.
#
# These tests are *invariants*, not behaviour-change tests: they go GREEN on
# author and stay GREEN as long as the locked frontmatter values do not drift.
# A future commit that demotes architect or security-engineer off Opus, or
# introduces a `model_conditional` block on those two roles, or breaks the
# review-role uniformity contract, will turn one of these RED.
#
# `model_conditional` is *explicitly excluded* from the uniformity comparison
# so that slice B's later addition of `model_conditional` to code-reviewer.md
# (and only code-reviewer.md) does not break this lock. See plan Q4 / MED-6.
# ---------------------------------------------------------------------------

REVIEW_ROLE_AGENTS = (
    "code-reviewer",
    "security-engineer",
    "patch-critic",
    "spec-blind-validator",
)

UNIFORMITY_FIELDS = ("min_confidence", "memory")


def _frontmatter_for(agent_name: str) -> dict:
    return _parse_frontmatter(AGENTS_DIR / f"{agent_name}.md")


class ArchitectAndSecurityEngineerModelLocks(unittest.TestCase):
    """architect and security-engineer are hard-locked at Opus and may NOT
    carry a `model_conditional` block — design and security judgement are
    monolithic and never demoted on a budget threshold.
    """

    def test_architect_model_locked_opus(self):
        fm = _frontmatter_for("architect")
        self.assertEqual(
            fm.get("model"), "opus",
            "agents/architect.md: model MUST remain 'opus'; architect is "
            "hard-locked per CLAUDE.md § Agent Team and plan AC-E2-1.",
        )
        self.assertNotIn(
            "model_conditional", fm,
            "agents/architect.md: must NOT declare a 'model_conditional' "
            "block. Architect is never demoted on Complexity Budget.",
        )

    def test_security_engineer_model_locked_opus(self):
        fm = _frontmatter_for("security-engineer")
        self.assertEqual(
            fm.get("model"), "opus",
            "agents/security-engineer.md: model MUST remain 'opus'; "
            "security-engineer is hard-locked per CLAUDE.md § Agent Team "
            "and plan AC-E2-1.",
        )
        self.assertNotIn(
            "model_conditional", fm,
            "agents/security-engineer.md: must NOT declare a "
            "'model_conditional' block. Security review is never demoted "
            "on Complexity Budget.",
        )


class ReviewRoleFrontmatterUniformity(unittest.TestCase):
    """The four review-role agents share `min_confidence` + `memory`. The
    `model_conditional` field is intentionally excluded so that slice B can
    add it to code-reviewer.md alone without tripping uniformity.
    """

    def test_review_role_frontmatter_uniformity_preserved(self):
        observed = {
            agent: {field: _frontmatter_for(agent).get(field)
                    for field in UNIFORMITY_FIELDS}
            for agent in REVIEW_ROLE_AGENTS
        }
        for field in UNIFORMITY_FIELDS:
            values = {agent: observed[agent][field] for agent in REVIEW_ROLE_AGENTS}
            unique = set(values.values())
            self.assertEqual(
                len(unique), 1,
                f"Review-role uniformity violated on '{field}': {values!r}. "
                f"The four review roles {list(REVIEW_ROLE_AGENTS)} must share "
                f"this field. 'model_conditional' is excluded by design.",
            )


# ---------------------------------------------------------------------------
# Slice E1 (model-demotion-pass-2026-05): CLAUDE.md Agent Team table contract.
#
# AC-E1: planning-agent row Default Model = haiku.
# AC-E2: code-reviewer row Default Model = "opus [1]" + footnote referencing
#        model_conditional and resolve_model_conditional.
# ---------------------------------------------------------------------------

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _agent_team_row(agent: str) -> str:
    """Return the Agent Team table row for `agent` (raw markdown line)."""
    text = CLAUDE_MD.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and f"| {agent} |" in stripped:
            return stripped
    raise AssertionError(f"CLAUDE.md: no Agent Team row found for {agent!r}")


class SliceE1ClaudeMdAgentTeamTable(unittest.TestCase):
    def test_claude_md_planning_agent_row_is_haiku(self):
        row = _agent_team_row("planning-agent")
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        # Expected columns: Agent | Phase | Worktree | Default Model | Tunable
        self.assertEqual(cells[0], "planning-agent")
        self.assertEqual(
            cells[1], "Build (advisory)",
            f"planning-agent row Phase column drifted: {cells!r}",
        )
        self.assertEqual(
            cells[3], "haiku",
            f"planning-agent row Default Model column must be 'haiku' "
            f"(case-sensitive); got {cells[3]!r}",
        )
        self.assertEqual(
            cells[4], "No",
            f"planning-agent row Tunable column drifted: {cells!r}",
        )

    def test_claude_md_code_reviewer_row_has_footnote(self):
        row = _agent_team_row("code-reviewer")
        self.assertIn(
            "opus [1]", row,
            f"code-reviewer row Default Model must read 'opus [1]'; "
            f"got row: {row!r}",
        )
        text = CLAUDE_MD.read_text()
        # Footnote must appear below the Agent Team table and reference both
        # the agent frontmatter field and the resolver implementation.
        self.assertIn(
            "model_conditional", text,
            "CLAUDE.md: footnote [1] must reference 'model_conditional'",
        )
        self.assertIn(
            "resolve_model_conditional", text,
            "CLAUDE.md: footnote [1] must reference "
            "'resolve_model_conditional'",
        )


if __name__ == "__main__":
    unittest.main()
