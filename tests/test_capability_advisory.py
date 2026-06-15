"""Tests for s0 — capability advisory: distinct messages, once-per-session, suppress."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "_lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

import capability_advisory as ca


# ---------------------------------------------------------------------------
# AC6 — distinct advisories per status
# ---------------------------------------------------------------------------

def test_distinct_advisories_per_status():
    """needs-auth, absent, and unclassified advisories must differ and name server + fix."""
    needs_auth = ca.advisory_text_for_status("needs-auth", "DesignSync")
    absent = ca.advisory_text_for_status("absent", None)
    unclassified = ca.advisory_text_for_status("unclassified", "mystery-server")

    # All three must be distinct
    assert needs_auth != absent
    assert needs_auth != unclassified
    assert absent != unclassified

    # needs-auth must name the server and mention re-auth
    assert "DesignSync" in needs_auth
    assert "re-auth" in needs_auth or "authenticate" in needs_auth.lower()

    # absent must mention connecting a design MCP
    assert "design" in absent.lower() or "connect" in absent.lower()

    # unclassified must name the server
    assert "mystery-server" in unclassified


# ---------------------------------------------------------------------------
# AC6b — advisory emitted once per session (marker from stdin .session_id)
# ---------------------------------------------------------------------------

def test_advisory_once_per_session(tmp_path):
    """emit_once emits advisory first call; silently skips on second call same session."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    sid = "test-session-abc123"

    call_count = []

    def fake_emit(text):
        call_count.append(text)

    # First call should emit
    result1 = ca.emit_once("design-source", "absent", sid, str(marker_dir), emit_fn=fake_emit)
    assert result1 is True
    assert len(call_count) == 1

    # Second call same session must not emit
    result2 = ca.emit_once("design-source", "absent", sid, str(marker_dir), emit_fn=fake_emit)
    assert result2 is False
    assert len(call_count) == 1  # still only 1


# ---------------------------------------------------------------------------
# AC6c — suppress entry in capability-map.json silences a class
# ---------------------------------------------------------------------------

def test_suppress_entry_silences_class(tmp_path):
    """When suppress:[design-source] in map, emit_once no-ops for that class."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    cap_map = tmp_path / "capability-map.json"
    cap_map.write_text(json.dumps({"schema_version": 1, "suppress": ["design-source"]}))

    call_count = []

    def fake_emit(text):
        call_count.append(text)

    suppress_list = ca.load_suppress_list(str(cap_map))
    result = ca.emit_once(
        "design-source", "absent", "sess-xyz", str(marker_dir),
        emit_fn=fake_emit, suppress_list=suppress_list,
    )
    assert result is False
    assert len(call_count) == 0
