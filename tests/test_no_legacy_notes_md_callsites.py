"""AC12 — All four legacy notes.md callsites updated.

Repo grep asserts 'notes.md' appears ONLY in allowlisted paths:
- scripts/migrate-session-memory-split.sh
- hooks/_lib/session-store.sh / session-store-sync.sh (reader-fallback)
- tests/ (any test file)
- CHANGELOG / README historical references
- pipeline-state/ (in-flight or archived plan/state files)
- learning/, agent-memory/, session-memory/ (data directories)
- .git/ (history)
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWLIST_PREFIXES = (
    "scripts/migrate-session-memory-split.sh",
    "scripts/migrate-pipeline-state.sh",  # historical references
    "hooks/_lib/session-store.sh",
    "hooks/_lib/session-store-sync.sh",
    "hooks/_lib/session-memory-read-split.sh",
    "tests/",
    "CHANGELOG",
    "README",
    "pipeline-state/",
    "learning/",
    "agent-memory/",
    "session-memory/",
    ".git/",
    ".claude-sessions/",
    ".claude/worktrees/",
    "protocols/autonomous-intelligence.md",  # historical migration doc
    "protocols/_proposals/",  # design proposals may discuss notes.md by name
    "eval/cases/",  # frozen historical snapshots — never edit
)

# These four callsites MUST have been updated (no longer reference notes.md
# the old way).
ENUMERATED_FORBIDDEN_CALLSITES = (
    "hooks/session-start-bootstrap.sh",
    "skills/batch-pipeline/SKILL.md",
    "orchestrator/pipeline-orchestration.md",
    "skills/internal-eval/run/ISOLATION.md",
)


def _is_allowlisted(path):
    rel = str(path)
    return any(rel.startswith(p) or f"/{p}" in f"/{rel}" for p in ALLOWLIST_PREFIXES)


class FourEnumeratedCallsitesUpdated(unittest.TestCase):
    def test_no_notes_md_in_session_start_bootstrap(self):
        path = ROOT / "hooks" / "session-start-bootstrap.sh"
        self.assertNotIn("notes.md", path.read_text())

    def test_no_notes_md_in_batch_pipeline_skill(self):
        path = ROOT / "skills" / "batch-pipeline" / "SKILL.md"
        self.assertNotIn("notes.md", path.read_text())

    def test_no_notes_md_in_pipeline_orchestration(self):
        path = ROOT / "orchestrator" / "pipeline-orchestration.md"
        self.assertNotIn("notes.md", path.read_text())

    def test_no_notes_md_in_internal_eval_isolation(self):
        path = ROOT / "skills" / "internal-eval" / "run" / "ISOLATION.md"
        self.assertNotIn("notes.md", path.read_text())


class NotesMdOnlyInAllowlistedPaths(unittest.TestCase):
    def test_notes_md_only_in_allowlisted_paths(self):
        # Use git ls-files so we only inspect tracked files (filters .git/).
        result = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-l", "notes.md"],
            capture_output=True, text=True,
        )
        files = [l for l in result.stdout.splitlines() if l.strip()]
        leaks = [f for f in files if not _is_allowlisted(Path(f))]
        self.assertEqual(
            leaks, [],
            f"notes.md leaked into non-allowlisted paths: {leaks}",
        )


if __name__ == "__main__":
    unittest.main()
