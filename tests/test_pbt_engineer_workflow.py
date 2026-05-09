"""AC2.5 — `pbt-engineer` documents the per-function workflow.

Asserts the agent body contains the workflow markers (identify candidate,
60s, freeze, justify) AND references the Slice-1 language-framework
table as its harness-selection source.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"

WORKFLOW_MARKERS = ("identify candidate", "60s", "freeze", "justif")


def test_agent_documents_per_function_workflow():
    body = AGENT_PATH.read_text().lower()
    missing = [m for m in WORKFLOW_MARKERS if m not in body]
    assert not missing, (
        f"pbt-engineer body missing workflow markers: {missing!r}")
    # Reference to the language-framework table in the new skill.
    assert "property-based-test" in body and "language" in body, (
        "pbt-engineer body must reference the Slice-1 language-framework "
        "table from the /property-based-test skill")
