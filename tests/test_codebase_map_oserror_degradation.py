"""AC21 [H2 broadened]: OSError dlopen-arch-mismatch degrades gracefully.

The generator child running inside the harness hook MUST tolerate the
full failure surface of `tree_sitter_languages`:

- `ImportError` — package missing entirely
- `OSError` — `dlopen` arch mismatch / missing shared library
- `SystemError` — fatal native abort surfaced as Python exception
- non-zero subprocess exit (covers SIGSEGV that does not raise a
  Python exception)

This test simulates the OSError case directly by mocking
`tree_sitter_languages.get_parser` to raise. The CLI module catches the
OSError, emits a stderr warning, and exits 0 — so the parent hook
treats the rebuild as a no-op.

Plan: § Slice C AC21.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class Ac21OsErrorDlopenArchMismatchDegradesGracefully(unittest.TestCase):
    """Mock get_parser → OSError; assert hook exits 0 + stderr warning."""

    def test_ac21_oserror_dlopen_arch_mismatch_degrades_gracefully(self):
        repo = Path(tempfile.mkdtemp(prefix="cbm-os-"))
        cache = Path(tempfile.mkdtemp(prefix="cbm-osc-"))
        try:
            (repo / "x.ts").write_text("export const x = 1;\n")

            # Build a small launcher that imports a fake tree_sitter_languages
            # module raising OSError("dlopen: arch mismatch") at import time.
            launcher = repo / "_launcher.py"
            launcher.write_text(textwrap.dedent(
                f"""
                import sys
                # Inject a fake tree_sitter_languages that raises OSError
                # on get_parser. This mirrors the dlopen-arch-mismatch
                # production failure mode.
                fake = type(sys)("tree_sitter_languages")
                def _fake_get_parser(lang):
                    raise OSError("dlopen: arch mismatch")
                fake.get_parser = _fake_get_parser
                sys.modules["tree_sitter_languages"] = fake
                # Now invoke the codebase_map CLI as if from the hook.
                sys.path.insert(0, {str(REPO_ROOT)!r})
                from codebase_map import cli
                rc = cli.main(["build", {str(repo)!r}, {str(cache)!r}])
                sys.exit(rc)
                """
            ).strip())

            result = subprocess.run(
                [sys.executable, str(launcher)],
                capture_output=True,
                timeout=20,
            )
            # The CLI MUST exit 0 even when the native lib is broken.
            self.assertEqual(
                result.returncode,
                0,
                f"CLI must exit 0 on OSError; got {result.returncode}, "
                f"stderr={result.stderr.decode(errors='replace')!r}",
            )
            # Stderr SHOULD carry a degradation warning.
            stderr = result.stderr.decode(errors="replace")
            self.assertRegex(
                stderr,
                r"codebase-map.*(unavailable|dlopen|degraded|skip)",
                "expected a stderr warning naming codebase-map degradation",
            )
        finally:
            import shutil
            shutil.rmtree(repo, ignore_errors=True)
            shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
