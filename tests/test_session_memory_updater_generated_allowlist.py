"""Gap 6 — session-memory-updater-dispatch.sh uses a _GENERATED_ARTIFACTS
allowlist for future-proofing.

Today the allowlist contains exactly one entry — `codebase-map` — matching
the historical hard-coded refusal. Refactoring to an iterable array makes
adding a second generator-owned artifact a one-line edit.

This test pins:
1. The dispatch script declares a `_GENERATED_ARTIFACTS=( ... )` array
   (single source of truth — adding to the array adds to the refusal set).
2. The array contains exactly `codebase-map` today.
3. Behaviour is unchanged: dispatch with `codebase-map` still refuses with
   `generated_artifact_misroute`; dispatch with `patterns` still works.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISPATCH = ROOT / "hooks" / "_lib" / "session-memory-updater-dispatch.sh"


class GeneratedArtifactsAllowlistDeclared(unittest.TestCase):
    def test_array_declaration_present(self):
        """The script declares a `_GENERATED_ARTIFACTS=(...)` bash array."""
        body = DISPATCH.read_text()
        self.assertRegex(
            body, r"_GENERATED_ARTIFACTS=\([^)]*\)",
            msg="dispatch script must declare _GENERATED_ARTIFACTS array",
        )

    def test_array_contains_codebase_map(self):
        """Today the array contains exactly the historical entry."""
        body = DISPATCH.read_text()
        match = re.search(r"_GENERATED_ARTIFACTS=\(([^)]*)\)", body)
        self.assertIsNotNone(match, "array declaration not found")
        contents = match.group(1).strip()
        # Normalize: split on whitespace, strip quotes
        entries = [e.strip().strip('"').strip("'")
                   for e in contents.split() if e.strip()]
        self.assertEqual(
            entries, ["codebase-map"],
            msg=f"expected ['codebase-map'], got {entries}. "
                f"Add new entries to _GENERATED_ARTIFACTS and update this "
                f"assertion in lockstep.",
        )


class GeneratedArtifactRefusalBehaviourPreserved(unittest.TestCase):
    """Functional regression guard: refactor must not change observable behaviour."""

    def _run(self, *args):
        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch) / "x.md"
            target.write_text("stub")
            # Override the seed-on-miss arg if needed; we just exercise refusal.
            return subprocess.run(
                ["bash", str(DISPATCH), str(target), *args[1:]],
                capture_output=True, text=True,
                env={"HOME": scratch,
                     "CLAUDE_CONFIG_DIR": str(ROOT),
                     "PATH": "/usr/local/bin:/usr/bin:/bin"},
            )

    def test_codebase_map_section_still_refused(self):
        result = self._run("ignored-target", "codebase-map")
        self.assertEqual(result.returncode, 1,
                         msg=f"expected refusal (exit 1); stderr={result.stderr}")
        self.assertIn("generated_artifact_misroute",
                      result.stderr + result.stdout)

    def test_patterns_section_still_accepted(self):
        result = self._run("ignored-target", "patterns")
        self.assertEqual(
            result.returncode, 0,
            msg=f"patterns dispatch must still succeed; stderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
