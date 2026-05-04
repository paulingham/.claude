"""B6-AC7: orchestrator/agent-orchestration.md documents Executor Resolution.

Verifies the Spawn Procedure section names all three precedence layers
(CLAUDE_FORCE_OPUS, prefer_opus, frontmatter executor) and explicitly notes
the env var is session-scoped, not pipeline-scoped.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "orchestrator" / "agent-orchestration.md"


def _spawn_procedure_section():
    text = DOC.read_text()
    match = re.search(
        r"##\s+Spawn Procedure\b(.+?)(?=\n## |\Z)", text, re.DOTALL)
    return match.group(1) if match else ""


class ExecutorResolutionDocumentsPrecedenceAndScope(unittest.TestCase):
    def test_spawn_procedure_documents_executor_resolution_with_session_scope(self):
        body = _spawn_procedure_section()
        self.assertIn("Executor Resolution", body,
                      "Spawn Procedure must contain 'Executor Resolution' heading")
        self.assertIn("CLAUDE_FORCE_OPUS", body)
        self.assertIn("prefer_opus", body)
        self.assertIn("frontmatter", body.lower() if False else body)
        self.assertIn("executor:", body)
        self.assertIn("session-scoped, not pipeline-scoped", body)
        force_idx = body.index("CLAUDE_FORCE_OPUS")
        prefer_idx = body.index("prefer_opus")
        front_idx = body.lower().index("frontmatter")
        self.assertLess(force_idx, prefer_idx,
                        "CLAUDE_FORCE_OPUS must precede prefer_opus")
        self.assertLess(prefer_idx, front_idx,
                        "prefer_opus must precede frontmatter executor")




class OrchestrationDocSnippetUsesExpandedLoader(unittest.TestCase):
    def test_canonical_python_snippet_imports_expanded_loader(self):
        text = DOC.read_text()
        self.assertIn(
            "from agent_parent_chain import load_expanded_instinct_categories",
            text,
            "canonical Python snippet must import expanded loader")
        self.assertIn(
            "load_expanded_instinct_categories(subagent_type)",
            text,
            "canonical Python snippet must call expanded loader")


if __name__ == "__main__":
    unittest.main()
