"""AC-A2c: verify that modified hook files source harness-paths.sh before HARNESS_DATA/HARNESS_ROOT use."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _lines(relpath):
    return (REPO_ROOT / relpath).read_text().splitlines()


def _source_index(lines):
    """Return line index of the harness-paths.sh source line, or None."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "source" in stripped and "harness-paths.sh" in stripped:
            return i
    return None


def _first_harness_use(lines):
    """Return line index of first $HARNESS_DATA or $HARNESS_ROOT reference, or None."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "HARNESS_DATA" in stripped or "HARNESS_ROOT" in stripped:
            return i
    return None


def test_session_start_bootstrap_sources_harness_paths_before_harness_data():
    lines = _lines("hooks/session-start-bootstrap.sh")
    src = _source_index(lines)
    use = _first_harness_use(lines)
    assert src is not None, "harness-paths.sh not sourced in session-start-bootstrap.sh"
    assert use is not None, "No HARNESS_DATA/HARNESS_ROOT reference found"
    assert src < use, f"source harness-paths.sh (line {src+1}) must precede first HARNESS use (line {use+1})"


def test_observation_capture_sources_harness_paths_before_harness_root():
    lines = _lines("hooks/observation-capture.sh")
    src = _source_index(lines)
    use = _first_harness_use(lines)
    assert src is not None, "harness-paths.sh not sourced in observation-capture.sh"
    assert use is not None, "No HARNESS_ROOT reference found"
    assert src < use


def test_session_memory_updater_dispatch_sources_harness_paths_before_harness_root():
    lines = _lines("hooks/_lib/session-memory-updater-dispatch.sh")
    src = _source_index(lines)
    use = _first_harness_use(lines)
    assert src is not None, "harness-paths.sh not sourced in session-memory-updater-dispatch.sh"
    assert use is not None, "No HARNESS_ROOT reference found"
    assert src < use
