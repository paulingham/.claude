"""Wave-2 A4.2 — destructive-verb module test for main-branch-guard.

Python-port of tests/shell/test_destructive_verb_block.bats so the suite is
green on CI hosts that don't ship bats-core.

Verifies:
  - Each verb in destructive-verbs.txt blocks (exit 2) without confirmation token
  - Confirmation token within TTL allows the command through (back to standard MBG checks)
  - Confirmation token past TTL still blocks
  - Wrong confirmation token value blocks
  - JSONL violation record is written with source: "destructive-verb"
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "main-branch-guard.sh"


def _run(cmd: str, env_overrides: dict, home: Path, sid: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CLAUDE_SESSION_ID"] = sid
    env["CLAUDE_HOOK_PROFILE"] = "minimal"
    for var in ("CLAUDE_DESTRUCTIVE_CONFIRM", "CLAUDE_DESTRUCTIVE_CONFIRM_TS",
                "CLAUDE_DESTRUCTIVE_CONFIRM_TTL"):
        env.pop(var, None)
    env.update(env_overrides)
    return subprocess.run(["bash", str(HOOK)], input=payload, env=env,
                          capture_output=True, text=True)


class _GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".claude").mkdir()
        self.sid = f"dvb-test-{os.getpid()}-{id(self)}"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class DestructiveVerbsBlock(_GuardCase):
    """Each verb in destructive-verbs.txt blocks without confirmation."""

    DESTRUCTIVE = [
        "fly destroy my-app",
        "psql -c 'DROP TABLE users'",
        "psql -c 'TRUNCATE users'",
        "kubectl delete namespace prod",
        "git push --force-with-lease origin main",
        "rm -rf $HOME/important",
        "aws s3 rb s3://prod-bucket --force",
        "railway down",
        "gcloud sql instances delete prod-db",
        "echo volumeDelete vol_xxx",
    ]

    def test_each_verb_blocks(self):
        for cmd in self.DESTRUCTIVE:
            with self.subTest(cmd=cmd):
                result = _run(cmd, {}, self.tmp, self.sid)
                self.assertEqual(result.returncode, 2,
                                 msg=f"expected block for '{cmd}': {result.stderr}")
                self.assertIn("destructive verb", result.stderr)


class ConfirmationToken(_GuardCase):
    """Valid confirmation token within TTL bypasses the block."""

    DESTRUCTIVE_CMD = "psql -c 'TRUNCATE logs'"

    def test_no_token_blocks(self):
        result = _run(self.DESTRUCTIVE_CMD, {}, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)

    def test_valid_token_within_ttl_passes(self):
        result = _run(self.DESTRUCTIVE_CMD, {
            "CLAUDE_DESTRUCTIVE_CONFIRM": "I-have-a-restorable-backup-elsewhere",
            "CLAUDE_DESTRUCTIVE_CONFIRM_TS": str(int(time.time())),
        }, self.tmp, self.sid)
        self.assertEqual(result.returncode, 0,
                         msg=f"valid token must pass: {result.stderr}")

    def test_expired_token_blocks(self):
        result = _run(self.DESTRUCTIVE_CMD, {
            "CLAUDE_DESTRUCTIVE_CONFIRM": "I-have-a-restorable-backup-elsewhere",
            "CLAUDE_DESTRUCTIVE_CONFIRM_TS": str(int(time.time()) - 700),
        }, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)

    def test_wrong_token_blocks(self):
        result = _run(self.DESTRUCTIVE_CMD, {
            "CLAUDE_DESTRUCTIVE_CONFIRM": "yes-do-it",
            "CLAUDE_DESTRUCTIVE_CONFIRM_TS": str(int(time.time())),
        }, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)

    def test_short_ttl_override_honored(self):
        result = _run(self.DESTRUCTIVE_CMD, {
            "CLAUDE_DESTRUCTIVE_CONFIRM": "I-have-a-restorable-backup-elsewhere",
            "CLAUDE_DESTRUCTIVE_CONFIRM_TS": str(int(time.time()) - 30),
            "CLAUDE_DESTRUCTIVE_CONFIRM_TTL": "10",
        }, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)

    def test_non_numeric_ts_blocks(self):
        result = _run(self.DESTRUCTIVE_CMD, {
            "CLAUDE_DESTRUCTIVE_CONFIRM": "I-have-a-restorable-backup-elsewhere",
            "CLAUDE_DESTRUCTIVE_CONFIRM_TS": "not-a-number",
        }, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)


class ViolationLogged(_GuardCase):
    """JSONL record written with source: 'destructive-verb'."""

    def test_jsonl_record_written(self):
        result = _run("fly destroy my-app", {}, self.tmp, self.sid)
        self.assertEqual(result.returncode, 2)
        jsonl = self.tmp / ".claude" / "metrics" / self.sid / "main-branch-violations.jsonl"
        self.assertTrue(jsonl.is_file())
        record = json.loads(jsonl.read_text().splitlines()[0])
        self.assertEqual(record["source"], "destructive-verb")
        self.assertEqual(record["action"], "prevented")
        self.assertIn("fly destroy", record["command"])


class NonDestructivePassthrough(_GuardCase):
    """Non-destructive commands pass through unaffected."""

    def test_ls_passes(self):
        result = _run("ls -la", {}, self.tmp, self.sid)
        self.assertEqual(result.returncode, 0)

    def test_git_status_passes(self):
        result = _run("git status", {}, self.tmp, self.sid)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
