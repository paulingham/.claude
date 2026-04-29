"""bash-write-guard open(...) read-mode false-positive tests (wave4-S AC5, AC6).

Source: pipeline-state/wave4-S-plan.md → AC5 / AC6
Origin: false positive observed in this session — bash-write-guard.sh
blocked `python3 -c "open('settings.json')"` (read-only) because the
matches_python_open_write regex required `.json` AND `open(` AND a write
mode, but the upstream is_write_to_protected short-circuit ordering let
the `.json + open(` partial match through under some shapes.

These tests pin the new is_open_read_only early-return guard:
- AC5: read shapes (open(f), open(f, 'r'), open(f, 'rb')) MUST exit 0;
  write shapes (open(f, 'w'), open(f, 'a')) MUST exit 2.
- AC6: pre-existing protection scenarios (json.dump on .json,
  sed -i settings.json, >> settings.json, open(f,'wb')) STILL block.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "bash-write-guard.sh"


def _run(command):
    """Invoke the guard from /tmp so is_caller_in_worktree returns false.
    Both PWD and cwd must be /tmp — the guard checks git toplevel first."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc_env = {**os.environ, "PWD": "/tmp"}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=proc_env,
        cwd="/tmp",
    )


class OpenReadModesPassOpenWriteModesBlock(unittest.TestCase):
    """AC5: read modes pass, write modes block."""

    def test_open_no_mode_passes(self):
        # Bare open(f) defaults to read mode
        r = _run("python3 -c \"open('settings.json')\"")
        self.assertEqual(
            r.returncode, 0, f"open(f) read should pass: stderr={r.stderr}"
        )

    def test_open_explicit_r_passes(self):
        r = _run("python3 -c \"open('settings.json', 'r')\"")
        self.assertEqual(
            r.returncode, 0, f"open(f,'r') should pass: stderr={r.stderr}"
        )

    def test_open_rb_passes(self):
        r = _run("python3 -c \"open('settings.json', 'rb')\"")
        self.assertEqual(
            r.returncode, 0, f"open(f,'rb') should pass: stderr={r.stderr}"
        )

    def test_open_w_blocks(self):
        r = _run("python3 -c \"open('settings.json', 'w')\"")
        self.assertEqual(
            r.returncode, 2, f"open(f,'w') must block: stdout={r.stdout}"
        )

    def test_open_a_blocks(self):
        r = _run("python3 -c \"open('settings.json', 'a')\"")
        self.assertEqual(
            r.returncode, 2, f"open(f,'a') must block: stdout={r.stdout}"
        )


class ExistingWriteGuardCasesStillBlock(unittest.TestCase):
    """AC6: regression suite — none of the prior protections regress."""

    def test_json_dump_on_json_blocks(self):
        r = _run(
            "python3 -c \"import json; json.dump({}, open('settings.json','w'))\""
        )
        self.assertEqual(r.returncode, 2, f"json.dump must block: {r.stderr}")

    def test_sed_in_place_settings_json_blocks(self):
        r = _run("sed -i '' 's/foo/bar/' settings.json")
        self.assertEqual(r.returncode, 2, f"sed -i must block: {r.stderr}")

    def test_redirect_to_settings_json_blocks(self):
        r = _run("echo hi >> settings.json")
        self.assertEqual(r.returncode, 2, f">> redirect must block: {r.stderr}")

    def test_open_wb_blocks(self):
        r = _run("python3 -c \"open('settings.json', 'wb')\"")
        self.assertEqual(r.returncode, 2, f"open(f,'wb') must block: {r.stderr}")


if __name__ == "__main__":
    unittest.main()
