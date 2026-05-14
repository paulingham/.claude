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
        self.assertNotIn("Sonnet 4.6 only", body)

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


if __name__ == "__main__":
    unittest.main()
