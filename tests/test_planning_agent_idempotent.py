"""Test: same finding processed only once (idempotency via content-hash cursor)."""
import tempfile
from pathlib import Path
from scratchpad_diff import diff_new_findings, _content_hash

FINDING_CONTENT = "---\ncategory: warning\n---\nSomething fragile here.\n"


def test_finding_returned_once_then_not_again():
    """A finding is returned the first time, then skipped on subsequent polls (same hash)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        finding_file = scratchpad / "build-eng.md"
        finding_file.write_text(FINDING_CONTENT)
        cursor = Path(tmpdir) / "cursor.json"
        # First poll: finding is new
        first = diff_new_findings(scratchpad, cursor)
        assert len(first) == 1, "Finding must be returned on first poll"
        # Simulate cursor update (agent persists after processing).
        # NOTE: diff_new_findings auto-persists, so this is redundant but
        # documents the agent-side contract.
        from scratchpad_diff import _save_cursor, _load_cursor
        seen = _load_cursor(cursor)
        seen.add((finding_file.name, _content_hash(finding_file.read_bytes())))
        _save_cursor(cursor, seen)
        # Second poll: same file, same content — must be skipped
        second = diff_new_findings(scratchpad, cursor)
        assert len(second) == 0, "Same (filename, content_hash) must not be returned twice"


def test_modified_finding_returned_again():
    """A finding with changed content (new hash) is returned again on next poll."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        finding_file = scratchpad / "build-eng.md"
        finding_file.write_text(FINDING_CONTENT)
        cursor = Path(tmpdir) / "cursor.json"
        first = diff_new_findings(scratchpad, cursor)
        assert len(first) == 1
        from scratchpad_diff import _save_cursor, _load_cursor
        seen = _load_cursor(cursor)
        seen.add((finding_file.name, _content_hash(finding_file.read_bytes())))
        _save_cursor(cursor, seen)
        # Modify the file (new content = new hash)
        finding_file.write_text(FINDING_CONTENT + "\nExtra detail added.\n")
        second = diff_new_findings(scratchpad, cursor)
        assert len(second) == 1, "Modified finding (new content hash) must be returned"
