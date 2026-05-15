"""Observation-length-cap hook tests (slice A onward).

Slice A authors the companion proposal doc + its keyword assertion.
Slice D adds hook behaviour + settings.json wiring tests.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import skipUnless


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / "hooks" / "observation-length-cap.sh"
SETTINGS_PATH = REPO_ROOT / "settings.json"


class TestObservationLengthCapProposal(unittest.TestCase):
    """Slice A AC-A2: proposal doc exists and carries the load-bearing keywords."""

    def test_observation_length_cap_proposal_has_keywords(self):
        path = (Path(__file__).resolve().parents[1]
                / "protocols" / "_proposals"
                / "2026-05-14-observation-length-cap.md")
        self.assertTrue(path.exists(),
                        f"proposal missing: {path}")
        body = path.read_text()
        for keyword in ("would_truncate", "20%", "flip trigger", "50 events"):
            self.assertIn(keyword, body,
                          f"proposal body missing keyword: {keyword!r}")


def _run_hook(stdin_payload, env_overrides=None, claude_home=None):
    """Run the hook, returning (returncode, claude_home dir)."""
    home = claude_home or Path(tempfile.mkdtemp(prefix="obscap-"))
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
    env.pop("CLAUDE_SESSION_ID", None)
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    result = subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    return result, home


def _make_edit_payload(file_path, new_string):
    return json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "x",
            "new_string": new_string,
        },
    })


def _metrics_dir(home):
    return Path(home) / ".claude" / "metrics"


class TestObservationLengthCapHookFile(unittest.TestCase):
    def test_hook_file_executable(self):
        self.assertTrue(HOOK_PATH.exists(), f"missing: {HOOK_PATH}")
        self.assertTrue(os.access(HOOK_PATH, os.X_OK),
                        f"not executable: {HOOK_PATH}")

    @skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
    def test_hook_shellcheck_clean(self):
        result = subprocess.run(
            ["shellcheck", "-x", str(HOOK_PATH)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0,
                         f"shellcheck failed:\n{result.stdout}\n{result.stderr}")


class TestObservationLengthCapHookBehaviour(unittest.TestCase):
    def test_hook_ignores_non_session_memory_paths(self):
        payload = _make_edit_payload("/tmp/foo.md", "x" * 100)
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_ignore"})
        self.assertEqual(result.returncode, 0)
        out = _metrics_dir(home) / "test_ignore" / "observation-length-cap.jsonl"
        self.assertFalse(out.exists(),
                         f"jsonl should not be written for non-session-memory path: {out}")

    def test_1500_char_payload_logs_would_truncate_true(self):
        payload = _make_edit_payload(
            "/home/x/.claude/session-memory/abc/build-test.md", "x" * 1500)
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_1500"})
        self.assertEqual(result.returncode, 0)
        out = _metrics_dir(home) / "test_1500" / "observation-length-cap.jsonl"
        self.assertTrue(out.exists(), f"jsonl missing: {out}")
        rec = json.loads(out.read_text().strip().splitlines()[-1])
        self.assertEqual(rec["char_count"], 1500)
        self.assertEqual(rec["estimated_tokens"], 375)
        self.assertTrue(rec["would_truncate"])
        self.assertEqual(rec["cap_tokens"], 250)

    def test_500_char_payload_logs_would_truncate_false(self):
        payload = _make_edit_payload(
            "/home/x/.claude/session-memory/abc/patterns.md", "y" * 500)
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_500"})
        self.assertEqual(result.returncode, 0)
        out = _metrics_dir(home) / "test_500" / "observation-length-cap.jsonl"
        self.assertTrue(out.exists())
        rec = json.loads(out.read_text().strip().splitlines()[-1])
        self.assertEqual(rec["char_count"], 500)
        self.assertEqual(rec["estimated_tokens"], 125)
        self.assertFalse(rec["would_truncate"])

    def test_session_id_cascade_matches_observation_capture(self):
        # With env set
        payload = _make_edit_payload(
            "/home/x/.claude/session-memory/abc/fragility.md", "z" * 200)
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_xyz"})
        self.assertEqual(result.returncode, 0)
        expected = _metrics_dir(home) / "test_xyz" / "observation-length-cap.jsonl"
        self.assertTrue(expected.exists(), f"expected at: {expected}")

        # With env unset — falls through to uuidgen path; must NOT be metrics/unknown/
        result2, home2 = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": None})
        self.assertEqual(result2.returncode, 0)
        unknown_path = _metrics_dir(home2) / "unknown" / "observation-length-cap.jsonl"
        self.assertFalse(unknown_path.exists(),
                         "must NOT sink to metrics/unknown/")
        # Some session dir should exist under metrics/
        produced = list(_metrics_dir(home2).glob("*/observation-length-cap.jsonl"))
        self.assertEqual(len(produced), 1,
                         f"expected exactly one session dir, got: {produced}")
        self.assertNotEqual(produced[0].parent.name, "unknown")

    def test_hook_exits_zero_on_malformed_json_stdin(self):
        result, home = _run_hook("not-json", env_overrides={"CLAUDE_SESSION_ID": "test_bad"})
        self.assertEqual(result.returncode, 0)
        out = _metrics_dir(home) / "test_bad" / "observation-length-cap.jsonl"
        self.assertFalse(out.exists())

    def test_hook_exits_zero_on_missing_file_path(self):
        payload = json.dumps({"tool_name": "Edit",
                              "tool_input": {"new_string": "abc"}})
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_nofp"})
        self.assertEqual(result.returncode, 0)

    def test_hook_exits_zero_on_10kb_payload(self):
        payload = _make_edit_payload(
            "/home/x/.claude/session-memory/abc/build-test.md", "q" * 10240)
        result, home = _run_hook(payload, env_overrides={"CLAUDE_SESSION_ID": "test_10k"})
        self.assertEqual(result.returncode, 0)
        out = _metrics_dir(home) / "test_10k" / "observation-length-cap.jsonl"
        self.assertTrue(out.exists())
        rec = json.loads(out.read_text().strip().splitlines()[-1])
        self.assertTrue(rec["would_truncate"])


class TestSettingsJsonRegistration(unittest.TestCase):
    def test_settings_json_registers_cap_hook_under_edit_matcher(self):
        with SETTINGS_PATH.open() as f:
            settings = json.load(f)
        edit_entries = [
            e for e in settings["hooks"]["PostToolUse"]
            if e.get("matcher") == "Edit"
        ]
        self.assertTrue(edit_entries, "no PostToolUse Edit matcher entry")
        found = False
        for entry in edit_entries:
            for hook in entry.get("hooks", []):
                args = hook.get("args", [])
                cmdline = " ".join(args) if args else ""
                if "observation-length-cap.sh" in cmdline:
                    found = True
                    break
        self.assertTrue(found,
                        "observation-length-cap.sh not registered under Edit matcher")


class TestHookHeaderDocumentation(unittest.TestCase):
    def test_header_documents_event_definition_and_flip_trigger(self):
        head = "\n".join(HOOK_PATH.read_text().splitlines()[:40])
        for token in ("event :=", "50 events", "20%", "would_truncate"):
            self.assertIn(token, head,
                          f"hook header missing token: {token!r}")


if __name__ == "__main__":
    unittest.main()
