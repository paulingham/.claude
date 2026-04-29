"""hooks.jsonl subagent_type field tests (wave4-S AC3, AC4).

Source: pipeline-state/wave4-S-plan.md → AC3 / AC4
Origin: pipeline-state/wave4-R-forensics.md anomaly #3 (broken duration_ms;
adjacent observation: PreToolUse:Agent records lacked subagent_type, making
forensics impossible to attribute to a role).

These tests pin the caller-passes-positional-arg contract:
- AC3: an Agent-relevant hook (pre-agent-thinking.sh) records
  subagent_type populated from tool_input.subagent_type into hooks.jsonl.
- AC4: a non-Agent hook (bash-write-guard.sh) records ZERO mention of
  subagent_type — the JSON key is ABSENT (not ""), and json.loads
  succeeds on every line in the same hooks.jsonl file.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
THINKING_HOOK = REPO_ROOT / "hooks" / "pre-agent-thinking.sh"
BASH_GUARD_HOOK = REPO_ROOT / "hooks" / "bash-write-guard.sh"


def _run(hook, payload, env, cwd=None):
    proc_env = {**os.environ, **env}
    return subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=proc_env,
        cwd=cwd,
    )


class AgentHookRecordIncludesSubagentType(unittest.TestCase):
    """AC3: PreToolUse:Agent record carries subagent_type from tool_input."""

    def setUp(self):
        self.session = f"test-st-{uuid.uuid4().hex[:8]}"
        self.metrics = Path(tempfile.mkdtemp(prefix="metrics-"))
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_HOOK_LOG_DIR": str(self.metrics),
        }

    def tearDown(self):
        shutil.rmtree(self.metrics, ignore_errors=True)

    def test_pretoolse_agent_record_includes_subagent_type(self):
        payload = {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "software-engineer"},
        }
        r = _run(THINKING_HOOK, payload, self.env)
        self.assertEqual(r.returncode, 0, f"hook failed: {r.stderr}")
        log = self.metrics / self.session / "hooks.jsonl"
        self.assertTrue(log.exists(), f"hooks.jsonl missing: {log}")
        lines = [ln for ln in log.read_text().strip().splitlines() if ln]
        self.assertGreaterEqual(len(lines), 1)
        rec = json.loads(lines[-1])
        self.assertEqual(
            rec.get("subagent_type"),
            "software-engineer",
            f"subagent_type missing or wrong: {rec}",
        )


class BashHookRecordOmitsSubagentTypeKeyEntirely(unittest.TestCase):
    """AC4: non-Agent hook records OMIT the subagent_type key (not "")."""

    def setUp(self):
        self.session = f"test-omit-{uuid.uuid4().hex[:8]}"
        self.metrics = Path(tempfile.mkdtemp(prefix="metrics-"))
        # Force the Bash guard down a non-blocking path: a benign command
        # without protected extensions. PWD set to /tmp avoids worktree-allow.
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_HOOK_LOG_DIR": str(self.metrics),
            "PWD": "/tmp",
        }

    def tearDown(self):
        shutil.rmtree(self.metrics, ignore_errors=True)

    def test_bash_record_omits_subagent_type_key_entirely(self):
        bash_payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo benign"},
        }
        r1 = _run(BASH_GUARD_HOOK, bash_payload, self.env, cwd="/tmp")
        # Benign echo should exit 0
        self.assertEqual(r1.returncode, 0, f"bash guard misfired: {r1.stderr}")
        # Now run an Agent hook — should add a record WITH subagent_type
        agent_payload = {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "code-reviewer"},
        }
        r2 = _run(THINKING_HOOK, agent_payload, self.env, cwd="/tmp")
        self.assertEqual(r2.returncode, 0, f"agent hook failed: {r2.stderr}")
        log = self.metrics / self.session / "hooks.jsonl"
        self.assertTrue(log.exists(), f"hooks.jsonl missing: {log}")
        text = log.read_text()
        lines = [ln for ln in text.strip().splitlines() if ln]
        # Every line must be valid JSON (mixed records, same file — F8)
        records = []
        for ln in lines:
            records.append(json.loads(ln))  # raises if invalid
        self.assertGreaterEqual(len(records), 2, f"expected >=2 records: {records}")
        # Identify which is which by hook_name
        bash_records = [r for r in records if r.get("hook_name") == "bash-write-guard"]
        agent_records = [
            r for r in records if r.get("hook_name") == "pre-agent-thinking"
        ]
        self.assertGreaterEqual(len(bash_records), 1, f"no bash record in {records}")
        self.assertGreaterEqual(len(agent_records), 1, f"no agent record in {records}")
        # Bash record: key must be ABSENT entirely (not present as "")
        for br in bash_records:
            self.assertNotIn(
                "subagent_type", br,
                f"bash record must omit subagent_type entirely (per F6): {br}",
            )
        # Agent record: key MUST be present and populated
        for ar in agent_records:
            self.assertEqual(
                ar.get("subagent_type"),
                "code-reviewer",
                f"agent record subagent_type missing/wrong: {ar}",
            )


if __name__ == "__main__":
    unittest.main()
