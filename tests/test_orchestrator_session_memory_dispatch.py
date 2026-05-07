"""AC9 — Orchestrator dispatches N parallel updaters (one per sub-file).

The dispatch procedure documented in
orchestrator/agent-orchestration.md § Session Memory Update produces
N parallel Agent calls in a single message when N sub-files need updates,
where N ∈ {1..4} (active-work.md is excluded — orchestrator updates it
directly via session_store_put without an updater spawn).
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISPATCH_DOC = ROOT / "orchestrator" / "agent-orchestration.md"


def _session_memory_update_section():
    text = DISPATCH_DOC.read_text()
    start = text.find("### Session Memory Update")
    if start < 0:
        return None
    end_a = text.find("\n###", start + 1)
    end_b = text.find("\n##\n", start + 1)
    candidates = [c for c in (end_a, end_b) if c > 0]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


class DispatchDocIncludesPerSubfileTargetFileLiteral(unittest.TestCase):
    def test_dispatch_doc_section_present(self):
        self.assertIsNotNone(_session_memory_update_section())

    def test_dispatch_doc_includes_per_subfile_target_file_literal(self):
        section = _session_memory_update_section()
        self.assertIn("targetFile=", section)
        self.assertIn("build-test.md", section)
        self.assertIn("patterns.md", section)

    def test_dispatch_doc_says_parallel_spawns_in_single_message(self):
        section = _session_memory_update_section().lower()
        # Mention parallel-spawn dispatch (one message, N calls).
        self.assertTrue(
            "parallel" in section and "single message" in section,
            "dispatch doc must describe parallel spawns in a single message",
        )

    def test_active_work_excluded_from_updater_spawn(self):
        section = _session_memory_update_section()
        # active-work.md must be called out as orchestrator-direct, NOT
        # spawned as an updater.
        self.assertIn("active-work", section)
        self.assertIn("session_store_put", section)


if __name__ == "__main__":
    unittest.main()
