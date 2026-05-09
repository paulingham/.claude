"""AC2.4 — `pbt-engineer` documents worktree-reuse, naming fix-engineer precedent.

Asserts the agent body names worktree-reuse and references `fix-engineer`
as the precedent for write-capable subagents that operate in the prior
worktree.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"


def test_agent_documents_worktree_reuse():
    body = AGENT_PATH.read_text().lower()
    # Worktree-reuse marker — accept several phrasings.
    assert "worktree" in body and "reuse" in body, (
        "pbt-engineer body must document worktree reuse")
    # Fix-engineer precedent.
    assert "fix-engineer" in body, (
        "pbt-engineer body must reference fix-engineer as the worktree-reuse "
        "precedent")
