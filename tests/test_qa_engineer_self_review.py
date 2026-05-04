"""C3 — qa-engineer.md instinct_categories + self-review checklist (AC20, AC21)."""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
QA_AGENT = REPO_ROOT / "agents" / "qa-engineer.md"


def _frontmatter():
    text = QA_AGENT.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1))


def test_qa_engineer_instinct_categories_include_playwright_and_web_e2e():
    """AC20: qa-engineer's instinct_categories includes `playwright` AND `web-e2e`."""
    cats = _frontmatter().get("instinct_categories", [])
    assert "playwright" in cats, \
        f"`playwright` missing from qa-engineer instinct_categories: {cats}"
    assert "web-e2e" in cats, \
        f"`web-e2e` missing from qa-engineer instinct_categories: {cats}"


def test_qa_engineer_self_review_includes_web_e2e_check():
    """AC21: self-review section contains the literal web-E2E checklist phrase."""
    text = QA_AGENT.read_text()
    expected_phrase = (
        "Web E2E flows exist for changed behavior matching web trigger globs")
    assert expected_phrase in text, \
        (f"qa-engineer.md self-review missing web-E2E checklist phrase: "
         f"`{expected_phrase}`")
