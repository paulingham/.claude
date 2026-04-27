"""Disk-aware loader for instinct files (Wave 4-M, Slice 2).

Reads `{base}/{project_hash}/instincts/*.md` (project) and
`{base}/instincts/*.md` (global). Tolerates malformed files; never raises.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from instinct_loader import load_instincts


def _read_warnings(home):
    """Find first non-empty warnings file in HOME's session metrics dir."""
    metrics = Path(home) / ".claude" / "metrics"
    if not metrics.is_dir():
        return ""
    for sess in metrics.iterdir():
        f = sess / "instinct-injections.jsonl"
        if f.exists() and f.stat().st_size > 0:
            return f.read_text()
    return ""


def _write_instinct(dir_path, filename, frontmatter, body):
    dir_path.mkdir(parents=True, exist_ok=True)
    text = f"---\n{frontmatter}---\n{body}"
    (dir_path / filename).write_text(text)


def _ok_frontmatter(instinct_id="instinct-foo", confidence=0.7,
                    roles=None, domain="workflow"):
    roles = roles if roles is not None else ["software-engineer"]
    roles_yaml = "[" + ", ".join(roles) + "]"
    return (f"id: {instinct_id}\nconfidence: {confidence}\n"
            f"roles: {roles_yaml}\ndomain: {domain}\n")


def _pattern_body(text):
    return f"## Pattern\n{text}\n"


class LoaderReadsProjectDir(unittest.TestCase):
    def test_loader_reads_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project_dir = base / "abc123" / "instincts"
            _write_instinct(project_dir, "foo.md",
                            _ok_frontmatter(),
                            _pattern_body("Validate at boundary."))
            result = load_instincts("abc123", instincts_base=base)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "instinct-foo")
            self.assertEqual(result[0]["scope"], "project")
            self.assertEqual(result[0]["pattern_summary"],
                             "Validate at boundary.")


class LoaderReadsGlobalDir(unittest.TestCase):
    def test_loader_reads_global_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_instinct(base / "instincts", "global-foo.md",
                            _ok_frontmatter(instinct_id="instinct-global"),
                            _pattern_body("Global pattern body."))
            result = load_instincts("abc123", instincts_base=base)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "instinct-global")
            self.assertEqual(result[0]["scope"], "global")


class LoaderPatternBodyExtraction(unittest.TestCase):
    def test_loader_pattern_body_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            body = ("## Context\nSome context here.\n\n"
                    "## Pattern\nLong sentence here.\n\n"
                    "## Why\nReason.\n")
            _write_instinct(base / "abc" / "instincts", "f.md",
                            _ok_frontmatter(), body)
            result = load_instincts("abc", instincts_base=base)
            self.assertEqual(result[0]["pattern_summary"],
                             "Long sentence here.")


class LoaderPatternBodyMultiLine(unittest.TestCase):
    def test_loader_pattern_body_multi_line_first_line_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            body = "## Pattern\nFirst line here.\nSecond line.\nThird line.\n"
            _write_instinct(base / "abc" / "instincts", "f.md",
                            _ok_frontmatter(), body)
            result = load_instincts("abc", instincts_base=base)
            self.assertEqual(result[0]["pattern_summary"], "First line here.")


class LoaderSkipsMissingConfidence(unittest.TestCase):
    def test_loader_skips_missing_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            bad = "id: instinct-bad\nroles: [a]\ndomain: x\n"
            _write_instinct(base / "abc" / "instincts", "bad.md",
                            bad, _pattern_body("Body."))
            with patch.dict(os.environ, {"HOME": str(home),
                                         "CLAUDE_SESSION_ID": "test-sess"}):
                result = load_instincts("abc", instincts_base=base)
                warnings = _read_warnings(home)
            self.assertEqual(result, [])
            self.assertIn("missing-confidence-field", warnings)


class LoaderSkipsMissingRoles(unittest.TestCase):
    def test_loader_skips_missing_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            bad = "id: instinct-bad\nconfidence: 0.7\ndomain: x\n"
            _write_instinct(base / "abc" / "instincts", "bad.md",
                            bad, _pattern_body("Body."))
            with patch.dict(os.environ, {"HOME": str(home),
                                         "CLAUDE_SESSION_ID": "test-sess"}):
                result = load_instincts("abc", instincts_base=base)
                warnings = _read_warnings(home)
            self.assertEqual(result, [])
            self.assertIn("missing-roles-field", warnings)


class LoaderSkipsMalformedYaml(unittest.TestCase):
    def test_loader_skips_malformed_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            project_dir = base / "abc" / "instincts"
            project_dir.mkdir(parents=True)
            (project_dir / "bad.md").write_text(
                "---\n{ unclosed mapping\n---\n## Pattern\nBody.\n")
            with patch.dict(os.environ, {"HOME": str(home),
                                         "CLAUDE_SESSION_ID": "test-sess"}):
                result = load_instincts("abc", instincts_base=base)
                warnings = _read_warnings(home)
            self.assertEqual(result, [])
            self.assertIn("malformed-yaml", warnings)


class LoaderSkipsMissingPatternHeading(unittest.TestCase):
    def test_loader_skips_missing_pattern_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            _write_instinct(base / "abc" / "instincts", "no-pattern.md",
                            _ok_frontmatter(),
                            "## Context\nNo pattern section here.\n")
            with patch.dict(os.environ, {"HOME": str(home),
                                         "CLAUDE_SESSION_ID": "test-sess"}):
                result = load_instincts("abc", instincts_base=base)
                warnings = _read_warnings(home)
            self.assertEqual(result, [])
            self.assertIn("missing-or-empty-pattern-body", warnings)


class LoaderSkipsEmptyPatternBody(unittest.TestCase):
    def test_loader_skips_empty_pattern_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            _write_instinct(base / "abc" / "instincts", "empty-body.md",
                            _ok_frontmatter(),
                            "## Pattern\n   \n\t\n\n## Why\nReason.\n")
            with patch.dict(os.environ, {"HOME": str(home),
                                         "CLAUDE_SESSION_ID": "test-sess"}):
                result = load_instincts("abc", instincts_base=base)
                warnings = _read_warnings(home)
            self.assertEqual(result, [])
            self.assertIn("missing-or-empty-pattern-body", warnings)


class LoaderProjectHashLocalSentinel(unittest.TestCase):
    def test_loader_project_hash_local_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = load_instincts("local", instincts_base=base)
            self.assertEqual(result, [])


class LoaderBothDirsMissing(unittest.TestCase):
    def test_loader_both_dirs_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = load_instincts("nonexistent-hash", instincts_base=base)
            self.assertEqual(result, [])


class LoaderUsesYamlSafeLoadNotPipelineFrontmatter(unittest.TestCase):
    def test_loader_uses_yaml_safe_load_not_pipeline_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_instinct(base / "abc" / "instincts", "list-roles.md",
                            _ok_frontmatter(roles=["a", "b", "c"]),
                            _pattern_body("Body."))
            result = load_instincts("abc", instincts_base=base)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["roles"], ["a", "b", "c"])
            self.assertIsInstance(result[0]["roles"], list)
            self.assertEqual(len(result[0]["roles"]), 3)


class LoaderDedupAcrossDirs(unittest.TestCase):
    def test_loader_dedup_across_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_instinct(base / "abc" / "instincts", "shared.md",
                            _ok_frontmatter(instinct_id="instinct-shared",
                                            confidence=0.4),
                            _pattern_body("Project version."))
            _write_instinct(base / "instincts", "shared.md",
                            _ok_frontmatter(instinct_id="instinct-shared",
                                            confidence=0.9),
                            _pattern_body("Global version."))
            result = load_instincts("abc", instincts_base=base)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["scope"], "project")
            self.assertEqual(result[0]["pattern_summary"], "Project version.")
