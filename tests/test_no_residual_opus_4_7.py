"""Slice A AC.1 — no residual ``opus-4-7`` outside the postmortem allowlist.

Authored RED-first (Step 1). Allowlist source: ``tests/_fixtures/postmortem_allowlist.yaml``.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — fall back to inline mini-parser
    yaml = None  # type: ignore[assignment]

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_ALLOWLIST = _REPO_ROOT / "tests" / "_fixtures" / "postmortem_allowlist.yaml"
_PATTERN = re.compile(r"opus-4-7")
_RANGE_RE = re.compile(r"L(\d+)-(\d+)")


def _load_allowlist() -> dict:
    text = _ALLOWLIST.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    raise unittest.SkipTest("PyYAML not installed")


def _is_exempt(path: pathlib.Path, lineno: int, line: str, allow: dict) -> bool:
    rel = path.relative_to(_REPO_ROOT).as_posix()
    for prefix in allow.get("paths", []) or []:
        if rel.startswith(prefix.rstrip("/") + "/") or rel == prefix.rstrip("/"):
            return True
    prose_map = allow.get("prose_tokens_in_file", {}) or {}
    for token in prose_map.get(rel, []) or []:
        if token in line:
            return True
    ranges_map = allow.get("inline_paragraphs", {}) or {}
    for spec in ranges_map.get(rel, []) or []:
        match = _RANGE_RE.match(spec)
        if match and int(match.group(1)) <= lineno <= int(match.group(2)):
            return True
    return False


def _rg_hits() -> list[tuple[pathlib.Path, int, str]]:
    result = subprocess.run(
        ["rg", "-n", "--no-messages", "opus-4-7", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hits: list[tuple[pathlib.Path, int, str]] = []
    for raw in result.stdout.splitlines():
        try:
            path_part, lineno_part, content = raw.split(":", 2)
        except ValueError:
            continue
        hits.append((_REPO_ROOT / path_part, int(lineno_part), content))
    return hits


class ZeroActiveConfigOccurrences(unittest.TestCase):
    """A.1 — ``rg 'opus-4-7'`` returns 0 hits outside the allowlist."""

    def test_zero_active_config_occurrences(self) -> None:
        allow = _load_allowlist()
        leaked: list[str] = []
        for path, lineno, content in _rg_hits():
            if not _is_exempt(path, lineno, content, allow):
                leaked.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}: {content[:80]}")
        self.assertEqual(leaked, [], f"residual opus-4-7 outside allowlist:\n" + "\n".join(leaked))


class PostmortemPreserved(unittest.TestCase):
    """A.1 — CLAUDE.md L47 literal ``Opus 4.7`` survives."""

    def test_postmortem_preserved(self) -> None:
        lines = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("Opus 4.7", lines[46], "CLAUDE.md:47 must retain literal 'Opus 4.7'")


class AllowlistFixtureWellFormed(unittest.TestCase):
    """A.1 — allowlist YAML loads and every entry resolves."""

    def test_allowlist_fixture_well_formed(self) -> None:
        allow = _load_allowlist()
        self.assertIsInstance(allow.get("paths", []), list)
        for prefix in allow.get("paths", []) or []:
            self.assertTrue(prefix.endswith("/"), f"path prefix must end with /: {prefix!r}")
        for spec_list in (allow.get("inline_paragraphs", {}) or {}).values():
            for spec in spec_list:
                match = _RANGE_RE.match(spec)
                self.assertIsNotNone(match, f"range must match L<n>-<m>: {spec!r}")
                self.assertLessEqual(int(match.group(1)), int(match.group(2)))


if __name__ == "__main__":
    unittest.main()
