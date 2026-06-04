"""Tool timing capture — AC1, AC2, AC3, AC4 tests.

Source: pipeline-state/tool-timing-capture-plan.md "Failing Test Stubs (per AC)".

These tests pin the contract for hooks/tool-timing-capture.sh:
- AC1: PostToolUse / PostToolUseFailure → one JSONL line per call to
  metrics/{sid}/tool-timings.jsonl with fields ts, tool, duration_ms,
  success, agent_role, task_id (in that order). json.dumps for safety.
  Missing optional fields are OMITTED, not null.
- AC2: runtime-guard.sh start-files + Mode B cap enforcement preserved
  (regression guards). Header comment is verbatim load-bearing.
- AC3: protocols/agent-protocol.md Resource Bounds section references the
  new hook, documents cleanup ownership, preserves Path-B disclosure.
  Mirror in protocols/parallel-dispatch-protocol.md is synced.
- AC4: tool-timing-capture.sh appears in test_log_hook.sh test 11
  enumerated hook list (asserted by test 11 itself).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "tool-timing-capture.sh"
RG_HOOK = REPO_ROOT / "hooks" / "runtime-guard.sh"
AGENT_PROTOCOL = REPO_ROOT / "protocols" / "agent-protocol.md"
PARALLEL_PROTOCOL = REPO_ROOT / "protocols" / "parallel-dispatch-protocol.md"


def _post_payload(tool="Bash", duration_ms=42, subagent_type=None,
                  task_id=None, hook_event_name="PostToolUse"):
    payload = {
        "hook_event_name": hook_event_name,
        "tool_name": tool,
        "duration_ms": duration_ms,
    }
    tool_input = {}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if tool_input:
        payload["tool_input"] = tool_input
    if task_id is not None:
        payload["_task_id"] = task_id
    return payload


_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(payload, env_extra=None, hook_path=HOOK, plugin_data=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    env = {**os.environ, "PYTHONPATH": merged_pp,
           "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if plugin_data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        env["HOME"] = str(plugin_data)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _read_timings(metrics_dir, session_id):
    p = Path(metrics_dir) / session_id / "tool-timings.jsonl"
    if not p.exists():
        return []
    return [line for line in p.read_text().splitlines() if line.strip()]


class TestToolTimingCapture(unittest.TestCase):
    """AC1 — capture hook writes JSONL lines with correct shape."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ttc-"))
        self.session = f"ttc-{uuid.uuid4().hex[:8]}"
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_HOOK_LOG_DIR": str(self.tmp),
            "HOME": str(self.tmp),
            "CLAUDE_PLUGIN_DATA": str(self.tmp),
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, payload, **extra):
        env = {**self.env, **extra}
        return _run_hook(payload, env_extra=env)

    def test_post_tool_use_success_writes_jsonl_line(self):
        """AC1: PostToolUse with all fields → one JSONL line, success=true."""
        payload = _post_payload(tool="Bash", duration_ms=123,
                                subagent_type="software-engineer")
        env = {"CLAUDE_PIPELINE_TASK_ID": "demo-task"}
        proc = self._run(payload, **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 1, f"expected 1 line, got {lines}")
        rec = json.loads(lines[0])
        self.assertEqual(rec["tool"], "Bash")
        self.assertEqual(rec["duration_ms"], 123)
        self.assertIs(rec["success"], True)
        self.assertEqual(rec["agent_role"], "software-engineer")
        self.assertEqual(rec["task_id"], "demo-task")
        self.assertIn("ts", rec)

    def test_post_tool_use_failure_writes_jsonl_line_with_success_false(self):
        """AC1: PostToolUseFailure → success=false."""
        payload = _post_payload(tool="Edit", duration_ms=77,
                                hook_event_name="PostToolUseFailure")
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertIs(rec["success"], False)
        self.assertEqual(rec["tool"], "Edit")

    def test_jsonl_injection_safe_for_quotes_backslash_newline(self):
        """AC1: Special chars in tool name still produce parseable JSON."""
        payload = _post_payload(
            tool='evil"\\\nname', duration_ms=1)
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["tool"], 'evil"\\\nname')

    def test_jsonl_field_order_matches_spec(self):
        """AC1: Field order in raw line is ts, tool, duration_ms, success,
        agent_role, task_id (anchors Open Question 1)."""
        payload = _post_payload(tool="Read", duration_ms=5,
                                subagent_type="qa-engineer")
        env = {"CLAUDE_PIPELINE_TASK_ID": "tid-7"}
        proc = self._run(payload, **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        line = lines[0]
        positions = [
            line.index('"ts"'),
            line.index('"tool"'),
            line.index('"duration_ms"'),
            line.index('"success"'),
            line.index('"agent_role"'),
            line.index('"task_id"'),
        ]
        self.assertEqual(positions, sorted(positions),
                         f"field order wrong: {line}")

    def test_missing_agent_role_and_task_id_omitted_not_null(self):
        """AC1: When neither subagent_type nor task_id is present, both keys
        are OMITTED from the JSON object (not written as null)."""
        payload = _post_payload(tool="Glob", duration_ms=2)
        env = {"CLAUDE_PIPELINE_TASK_ID": ""}
        proc = self._run(payload, **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertNotIn("agent_role", rec)
        self.assertNotIn("task_id", rec)
        self.assertEqual(rec["tool"], "Glob")

    def test_metrics_dir_auto_created_when_absent(self):
        """AC1: hook creates metrics/{sid}/ if it does not exist."""
        # tmp dir exists but no session subdir yet
        self.assertFalse((self.tmp / self.session).exists())
        payload = _post_payload(tool="Bash", duration_ms=1)
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.tmp / self.session).is_dir())

    def test_session_id_sanitized_against_path_traversal(self):
        """AC1: ../../../etc/passwd session id stays inside metrics dir."""
        env = {
            "CLAUDE_SESSION_ID": "../../../etc/passwd",
            "CLAUDE_HOOK_LOG_DIR": str(self.tmp),
            "HOME": str(self.tmp),
        }
        payload = _post_payload(tool="Bash", duration_ms=1)
        proc = _run_hook(payload, env_extra=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # The traversal-attempted path must not exist outside tmp
        outside = self.tmp.parent / "etc" / "passwd"
        self.assertFalse(outside.exists())
        # Some tool-timings.jsonl must exist under tmp (sanitized session)
        found = list(self.tmp.rglob("tool-timings.jsonl"))
        self.assertTrue(found, "expected tool-timings.jsonl under tmp")

    def test_missing_duration_ms_skips_emission_silently(self):
        """AC1: malformed payload (no duration_ms) → exit 0, no JSONL line."""
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash"}
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(lines, [])

    def test_telemetry_jsonl_line_emitted_via_log_hook_contract(self):
        """AC1: hook itself emits one entry to hooks.jsonl via _log.sh."""
        payload = _post_payload(tool="Bash", duration_ms=1)
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hooks_log = self.tmp / self.session / "hooks.jsonl"
        self.assertTrue(hooks_log.exists(),
                        f"expected hooks.jsonl at {hooks_log}")
        lines = [ln for ln in hooks_log.read_text().splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["hook_name"], "tool-timing-capture")

    def test_repeated_calls_append_distinct_lines(self):
        """Mutation guard: file open mode is 'a' (append), not 'w' (overwrite),
        and lines are newline-terminated so splitlines() yields N records."""
        for i, tool in enumerate(("Bash", "Read", "Edit")):
            self._run(_post_payload(tool=tool, duration_ms=i + 1))
        lines = _read_timings(self.tmp, self.session)
        self.assertEqual(len(lines), 3, f"expected 3 lines, got {lines}")
        tools = [json.loads(ln)["tool"] for ln in lines]
        self.assertEqual(tools, ["Bash", "Read", "Edit"])


class TestRuntimeGuardPreserved(unittest.TestCase):
    """AC2 — runtime-guard.sh behaviour and header are preserved."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rg-"))
        self.plugin_data = Path(tempfile.mkdtemp(prefix="rg-pd-"))
        self.session = f"rg-{uuid.uuid4().hex[:8]}"
        self.state_dir = self.tmp / "pipeline-state"
        self.state_dir.mkdir()
        (self.state_dir / "demo-pipeline.md").write_text(
            "---\ntask_id: demo\nphase: build\nverdict: in_progress\n---\n"
        )
        # seed pipeline-state in plugin_data for stop-hook discovery
        pd_ps = self.plugin_data / "pipeline-state"
        pd_ps.mkdir(parents=True)
        (pd_ps / "demo-pipeline.md").write_text(
            "---\ntask_id: demo\nphase: build\nverdict: in_progress\n---\n"
        )
        self.metrics = self.plugin_data / "metrics" / self.session
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_PIPELINE_STATE_DIR": str(self.state_dir),
            "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
            "HOME": str(self.plugin_data),
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def test_runtime_guard_start_files_still_written_for_in_flight_caps(self):
        """AC2: Mode A on Agent payload still creates <key>.start file."""
        payload = {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "qa-engineer"},
        }
        proc = _run_hook(payload, env_extra=self.env, hook_path=RG_HOOK)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        runtime_dir = self.metrics / "subagent-runtimes"
        self.assertTrue(runtime_dir.is_dir(),
                        f"expected start dir at {runtime_dir}")
        start_files = list(runtime_dir.glob("*.start"))
        self.assertEqual(len(start_files), 1,
                         f"expected one .start, got {start_files}")

    def test_runtime_guard_mode_b_still_blocks_over_cap(self):
        """AC2: Mode B with stale start-file emits exit 2 + shutdown directive."""
        runtime_dir = self.metrics / "subagent-runtimes"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        # Write a fake stale start-file (1801s old)
        stale_ts = int(time.time()) - 1801
        key_file = runtime_dir / "stalekey.start"
        key_file.write_text(f"{stale_ts}:subagent:fake-subagent\n")
        payload = {"tool_name": "Bash",
                   "tool_input": {"command": "echo hello"}}
        proc = _run_hook(payload, env_extra=self.env, hook_path=RG_HOOK)
        self.assertEqual(proc.returncode, 2,
                         f"expected exit 2, got {proc.returncode} "
                         f"stderr={proc.stderr}")
        self.assertTrue(proc.stderr.strip(),
                        "expected stderr shutdown directive")

    def test_runtime_guard_header_comment_references_tool_timings_jsonl(self):
        """AC2: header comment is verbatim two-line block."""
        text = RG_HOOK.read_text()
        self.assertIn(
            "# Historical per-call durations are captured separately by "
            "hooks/tool-timing-capture.sh",
            text,
        )
        self.assertIn(
            "# to metrics/{session}/tool-timings.jsonl. This guard owns "
            "wall-clock cap ENFORCEMENT only.",
            text,
        )


class TestRulesUpdate(unittest.TestCase):
    """AC3 — protocols/agent-protocol.md and parallel-dispatch-protocol.md."""

    def setUp(self):
        self.agent_text = AGENT_PROTOCOL.read_text()
        self.parallel_text = PARALLEL_PROTOCOL.read_text()
        # Isolate just the Resource Bounds section for proximity assertions.
        self.bounds_section = self._extract_section(
            self.agent_text, "## Resource Bounds")

    @staticmethod
    def _extract_section(text, heading):
        start = text.index(heading)
        # Find the next top-level "## " heading after this one
        rest = text[start + len(heading):]
        m = re.search(r"\n## ", rest)
        end = start + len(heading) + (m.start() if m else len(rest))
        return text[start:end]

    def test_rules_agent_protocol_references_tool_timings_jsonl(self):
        """AC3a/b: tool-timings.jsonl AND tool-timing-capture.sh present."""
        self.assertIn("tool-timings.jsonl", self.bounds_section)
        self.assertIn("tool-timing-capture.sh", self.bounds_section)

    def test_rules_agent_protocol_documents_cleanup_hook_ownership(self):
        """AC3c: subagent-stop-trajectory.sh in proximity to 'cleanup' or
        '.start' (within 200 chars)."""
        section = self.bounds_section
        idx = 0
        found = False
        while True:
            i = section.find("subagent-stop-trajectory.sh", idx)
            if i == -1:
                break
            window = section[max(0, i - 200): i + len(
                "subagent-stop-trajectory.sh") + 200]
            if "cleanup" in window or ".start" in window:
                found = True
                break
            idx = i + 1
        self.assertTrue(
            found,
            "subagent-stop-trajectory.sh must appear near 'cleanup' "
            "or '.start' in Resource Bounds section",
        )

    def test_rules_agent_protocol_path_b_disclosure_preserved(self):
        """AC3d: Path-B disclosure substrings preserved verbatim."""
        self.assertIn(
            "out-of-band kill is not currently exposed by the Agent "
            "tool input schema",
            self.bounds_section,
        )
        self.assertIn(
            "next tool the runaway subagent attempts is refused",
            self.bounds_section,
        )

    def test_rules_parallel_dispatch_mirror_synced(self):
        """AC3: parallel-dispatch-protocol.md mirror references the new file."""
        # Find the Resource Bounds section in parallel-dispatch-protocol.md
        section = self._extract_section(
            self.parallel_text, "## Resource Bounds")
        self.assertIn("tool-timings.jsonl", section)


if __name__ == "__main__":
    unittest.main()
