"""Tests for the deterministic new-finding pre-filter used by the
continuous planning agent.

Behavior contract:
- diff_new_findings returns [] when scratchpad_dir is missing.
- A finding present in the scratchpad but absent from cursor is returned.
- A finding whose (filename, content_hash) is already in cursor is NOT returned.
- A scratchpad file with malformed/missing frontmatter is silently skipped.
- The category field is parsed from YAML frontmatter (case- and whitespace-tolerant).
- Cursor persistence round-trips: save then load equals input.
"""
import json
import tempfile
import unittest
from pathlib import Path

from scratchpad_diff import (
    _content_hash,
    _load_cursor,
    _parse_finding,
    _save_cursor,
    commit_findings,
    diff_new_findings,
    peek_new_findings,
)


class DiffNewFindingsHandlesMissingScratchpadDir(unittest.TestCase):
    def test_returns_empty_when_scratchpad_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            cursor = Path(tmp) / "cursor.json"
            self.assertEqual(diff_new_findings(missing, cursor), [])


class DiffNewFindingsReturnsUnseenFindings(unittest.TestCase):
    def test_unseen_finding_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "build.md").write_text(
                "---\ncategory: fragility\n---\nAuthService is timing-sensitive.\n"
            )
            cursor = Path(tmp) / "cursor.json"
            results = diff_new_findings(scratch, cursor)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "build.md")
        self.assertEqual(results[0]["category"], "fragility")
        self.assertIn("AuthService", results[0]["body"])


class DiffNewFindingsSkipsAlreadySeenFindings(unittest.TestCase):
    def test_seen_finding_is_not_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            file_path = scratch / "build.md"
            file_path.write_text(
                "---\ncategory: warning\n---\ndb writes are not idempotent\n"
            )
            cursor = Path(tmp) / "cursor.json"
            first_pass = diff_new_findings(scratch, cursor)
            self.assertEqual(len(first_pass), 1)
            second_pass = diff_new_findings(scratch, cursor)
        self.assertEqual(second_pass, [])


class DiffNewFindingsReturnsRevisedFindingWhenContentChanges(unittest.TestCase):
    def test_modified_file_yields_new_hash_and_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            file_path = scratch / "build.md"
            file_path.write_text("---\ncategory: discovery\n---\nfirst body\n")
            cursor = Path(tmp) / "cursor.json"
            diff_new_findings(scratch, cursor)
            file_path.write_text("---\ncategory: discovery\n---\nsecond body\n")
            second_pass = diff_new_findings(scratch, cursor)
        self.assertEqual(len(second_pass), 1)
        self.assertIn("second body", second_pass[0]["body"])


class ParseFindingSkipsMalformedFrontmatter(unittest.TestCase):
    def test_missing_frontmatter_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.md"
            f.write_text("no frontmatter here, just plain body\n")
            self.assertIsNone(_parse_finding(f))

    def test_unclosed_frontmatter_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.md"
            f.write_text("---\ncategory: warning\nno closing delim\n")
            self.assertIsNone(_parse_finding(f))

    def test_frontmatter_without_category_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.md"
            f.write_text("---\nname: foo\n---\nbody\n")
            self.assertIsNone(_parse_finding(f))


class ParseFindingExtractsCategoryToleratingWhitespaceAndCase(unittest.TestCase):
    def test_uppercase_category_is_lowercased(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "ok.md"
            f.write_text("---\ncategory:   FRAGILITY\n---\nbody text\n")
            finding = _parse_finding(f)
        assert finding is not None
        self.assertEqual(finding["category"], "fragility")
        self.assertEqual(finding["body"].strip(), "body text")


class DiffNewFindingsIgnoresMalformedFiles(unittest.TestCase):
    def test_malformed_file_does_not_appear_in_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "good.md").write_text(
                "---\ncategory: pattern\n---\nworks well\n"
            )
            (scratch / "bad.md").write_text("plain text without frontmatter\n")
            cursor = Path(tmp) / "cursor.json"
            results = diff_new_findings(scratch, cursor)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "good.md")


class CursorRoundTrips(unittest.TestCase):
    def test_save_then_load_returns_same_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            cursor = Path(tmp) / "cursor.json"
            seen = {("a.md", "abc123"), ("b.md", "def456")}
            _save_cursor(cursor, seen)
            self.assertEqual(_load_cursor(cursor), seen)

    def test_load_missing_cursor_returns_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            cursor = Path(tmp) / "cursor.json"
            self.assertEqual(_load_cursor(cursor), set())


class ContentHashIsDeterministicAndShort(unittest.TestCase):
    def test_same_input_same_hash(self):
        self.assertEqual(_content_hash(b"hello"), _content_hash(b"hello"))

    def test_hash_is_16_hex_chars(self):
        h = _content_hash(b"any input")
        self.assertEqual(len(h), 16)
        int(h, 16)  # raises if not hex


class DiffNewFindingsNonExistentParentScratchpadStillReturnsEmpty(unittest.TestCase):
    def test_passes_string_path_for_scratchpad_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "x.md").write_text(
                "---\ncategory: decision\n---\nrationale\n"
            )
            cursor = Path(tmp) / "cursor.json"
            # Pass strings, not Paths
            results = diff_new_findings(str(scratch), str(cursor))
        self.assertEqual(len(results), 1)


class PeekDoesNotAdvanceCursor(unittest.TestCase):
    """peek must NOT mutate the cursor — caller may crash before commit."""

    def test_peek_repeatedly_returns_same_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "a.md").write_text(
                "---\ncategory: warning\n---\nbe careful\n"
            )
            cursor = Path(tmp) / "cursor.json"
            first = peek_new_findings(scratch, cursor)
            second = peek_new_findings(scratch, cursor)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["content_hash"], second[0]["content_hash"])


class PeekReturnsEmptyWhenScratchpadMissing(unittest.TestCase):
    def test_missing_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                peek_new_findings(Path(tmp) / "nope", Path(tmp) / "cursor.json"),
                [],
            )


class CommitMarksFindingsSeen(unittest.TestCase):
    def test_after_commit_peek_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "a.md").write_text(
                "---\ncategory: discovery\n---\nfound something\n"
            )
            cursor = Path(tmp) / "cursor.json"
            findings = peek_new_findings(scratch, cursor)
            commit_findings(findings, cursor)
            self.assertEqual(peek_new_findings(scratch, cursor), [])

    def test_commit_empty_list_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            cursor = Path(tmp) / "cursor.json"
            commit_findings([], cursor)
            # Cursor file must not have been created from a no-op commit.
            self.assertFalse(cursor.exists())


class PeekThenCommitMatchesDiffWrapper(unittest.TestCase):
    """peek + commit must produce the same final state as diff_new_findings."""

    def test_split_api_equivalent_to_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            (scratch / "a.md").write_text(
                "---\ncategory: pattern\n---\nworks well\n"
            )
            cursor_split = Path(tmp) / "split.json"
            cursor_wrap = Path(tmp) / "wrap.json"

            split_first = peek_new_findings(scratch, cursor_split)
            commit_findings(split_first, cursor_split)
            wrap_first = diff_new_findings(scratch, cursor_wrap)

        self.assertEqual(len(split_first), len(wrap_first))
        self.assertEqual(
            split_first[0]["content_hash"], wrap_first[0]["content_hash"]
        )


if __name__ == "__main__":
    unittest.main()
