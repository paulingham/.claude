"""Slice 3: PreAgent instinct-injector hook (Path-B advisory).

Subprocess-based tests of `hooks/instinct-injector.sh`. The hook NEVER
blocks — exit code is always 0. Behaviour is observable via the JSONL
forensic file written under metrics/{session}/instinct-injections.jsonl.

Sessions are uniquely-named via uuid; we DO NOT patch HOME (subprocess
python loses access to user-site yaml when HOME is overridden, mirroring
test_pre_agent_allowlist.py).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "instinct-injector.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _make_env(plugin_data=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    env = {**os.environ, "PYTHONPATH": merged_pp,
           "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if plugin_data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        env["HOME"] = str(plugin_data)
    return env


def _run_hook(payload, env=None, plugin_data=None):
    proc_env = _make_env(plugin_data)
    proc_env.update(env or {})
    try:
        return subprocess.run(
            ["bash", str(HOOK)], input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=proc_env)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"hook timed out: {exc}") from exc


def _session_paths(base):
    session = f"test-instinct-{uuid.uuid4()}"
    root = base
    return session, root / "metrics" / session / "instinct-injections.jsonl"


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


def _yaml_list(values):
    return "\n".join(f"  - {v}" for v in values)


def _write_agent(agents_dir, role, categories):
    body = (f"---\nname: {role}\ninstinct_categories:\n"
            f"{_yaml_list(categories)}\n---\nbody\n")
    (agents_dir / f"{role}.md").write_text(body)


def _write_instinct(instincts_dir, slug, roles, confidence=0.6):
    instincts_dir.mkdir(parents=True, exist_ok=True)
    body = (f"---\nid: {slug}\nconfidence: {confidence}\nroles:\n"
            f"{_yaml_list(roles)}\n---\n\n## Pattern\nAlways do {slug}.\n")
    (instincts_dir / f"{slug}.md").write_text(body)


class _InstinctTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="instinct-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _paths(self):
        return _session_paths(base=self.plugin_data)

    def _run(self, payload, extra_env=None):
        return _run_hook(payload, env=extra_env, plugin_data=self.plugin_data)


class HookFastExitsOnNonAgentTool(_InstinctTestCase):
    def test_hook_fast_exits_on_non_agent_tool(self):
        session, log_path = self._paths()
        try:
            result = _run_hook({"tool_name": "Bash", "tool_input": {}},
                               env={"CLAUDE_SESSION_ID": session},
                               plugin_data=self.plugin_data)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "non-Agent tool should not create instinct log")
        finally:
            _cleanup(log_path)


class HookFastExitsOnMinimalProfile(_InstinctTestCase):
    def test_hook_fast_exits_on_minimal_profile(self):
        session, log_path = self._paths()
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "software-engineer"}}
        try:
            result = _run_hook(payload, env={"CLAUDE_SESSION_ID": session,
                                             "CLAUDE_HOOK_PROFILE": "minimal"},
                               plugin_data=self.plugin_data)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "minimal profile should suppress instinct log")
        finally:
            _cleanup(log_path)


class HookFastExitsWhenSubagentTypeMissing(_InstinctTestCase):
    def test_hook_fast_exits_when_subagent_type_missing(self):
        session, log_path = self._paths()
        try:
            result = _run_hook({"tool_name": "Agent", "tool_input": {}},
                               env={"CLAUDE_SESSION_ID": session},
                               plugin_data=self.plugin_data)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "missing subagent_type should not create log")
        finally:
            _cleanup(log_path)


class HookLogsLoggedWhenNoInstinctsDir(_InstinctTestCase):
    def test_hook_logs_logged_when_no_instincts_dir(self):
        session, log_path = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            empty_base = Path(tmp) / "learning"  # never created
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type": "software-engineer"}}
            try:
                result = _run_hook(payload, env={
                    "CLAUDE_SESSION_ID": session,
                    "CLAUDE_INSTINCTS_DIR": str(empty_base)},
                    plugin_data=self.plugin_data)
                self.assertEqual(result.returncode, 0)
                self.assertTrue(log_path.exists(),
                                f"expected log at {log_path}")
                record = json.loads(log_path.read_text().strip().splitlines()[-1])
                self.assertEqual(record["source"], "logged")
                self.assertEqual(record["agent_role"], "software-engineer")
                self.assertEqual(record["resolved"]["count_kept"], 0)
            finally:
                _cleanup(log_path)


class HookLogsLoggedWhenMatchesPresent(_InstinctTestCase):
    """Path-B contract: hook ALWAYS writes source='logged' on the success
    path. The 'orchestrator-injected' source is reserved exclusively for
    the orchestrator caller after a real prompt splice. Mismatch (logged
    without paired orchestrator-injected) is the Path-B failure surface
    detected by /forensics."""

    def test_hook_logs_logged_when_matches_present(self):
        session, log_path = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            base, agents = Path(tmp) / "learning", Path(tmp) / "agents"
            agents.mkdir()
            _write_agent(agents, "software-engineer", ["testing"])
            _write_instinct(base / "instincts", "test-discipline", ["testing"])
            try:
                result = _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": "software-engineer"}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_INSTINCTS_DIR": str(base),
                         "CLAUDE_AGENTS_DIR": str(agents)},
                    plugin_data=self.plugin_data)
                self.assertEqual(result.returncode, 0)
                record = json.loads(log_path.read_text().strip().splitlines()[-1])
                self.assertEqual(record["source"], "logged")
                self.assertGreaterEqual(record["resolved"]["count_kept"], 1)
                self.assertGreater(record["resolved"]["rendered_chars"], 0)
            finally:
                _cleanup(log_path)


class HookLogsLoadWarningOnMalformedInstinct(_InstinctTestCase):
    def test_hook_logs_load_warning_on_malformed_instinct_yaml(self):
        session, log_path = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            base, agents = Path(tmp) / "learning", Path(tmp) / "agents"
            agents.mkdir()
            (base / "instincts").mkdir(parents=True)
            (base / "instincts" / "broken.md").write_text(
                "---\nthis is: [unbalanced\n---\n## Pattern\nx\n")
            _write_agent(agents, "software-engineer", ["testing"])
            try:
                _run_hook({"tool_name": "Agent",
                           "tool_input": {"subagent_type": "software-engineer"}},
                          env={"CLAUDE_SESSION_ID": session,
                               "CLAUDE_INSTINCTS_DIR": str(base),
                               "CLAUDE_AGENTS_DIR": str(agents)},
                          plugin_data=self.plugin_data)
                lines = log_path.read_text().strip().splitlines()
                sources = [json.loads(ln)["source"] for ln in lines]
                self.assertIn("load-warning", sources)
            finally:
                _cleanup(log_path)


class HookHonoursMinConfidenceEnvOverride(_InstinctTestCase):
    def test_min_confidence_override_filters_low_confidence_instincts(self):
        session, log_path = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            base, agents = Path(tmp) / "learning", Path(tmp) / "agents"
            agents.mkdir()
            _write_agent(agents, "software-engineer", ["testing"])
            _write_instinct(base / "instincts", "weak", ["testing"], confidence=0.5)
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": "software-engineer"}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_INSTINCTS_DIR": str(base),
                         "CLAUDE_AGENTS_DIR": str(agents),
                         "CLAUDE_INSTINCT_MIN_CONFIDENCE": "0.9"},
                    plugin_data=self.plugin_data)
                record = json.loads(log_path.read_text().strip().splitlines()[-1])
                self.assertEqual(record["source"], "logged")
                self.assertEqual(record["resolved"]["count_kept"], 0)
                self.assertEqual(record["resolved"]["min_confidence"], 0.9)
            finally:
                _cleanup(log_path)


class HookFiltersInstinctsByAgentCategories(_InstinctTestCase):
    def test_instinct_with_unmatched_role_is_filtered_out(self):
        session, log_path = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            base, agents = Path(tmp) / "learning", Path(tmp) / "agents"
            agents.mkdir()
            _write_agent(agents, "software-engineer", ["security"])
            _write_instinct(base / "instincts", "test-only", ["testing"])
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": "software-engineer"}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_INSTINCTS_DIR": str(base),
                         "CLAUDE_AGENTS_DIR": str(agents)},
                    plugin_data=self.plugin_data)
                record = json.loads(log_path.read_text().strip().splitlines()[-1])
                self.assertEqual(record["source"], "logged")
                self.assertEqual(record["resolved"]["count_kept"], 0)
                self.assertEqual(record["resolved"]["instinct_categories"],
                                 ["security"])
            finally:
                _cleanup(log_path)


class HookNeverBlocksOnMalformedInput(unittest.TestCase):
    def test_hook_returns_zero_on_garbage_stdin(self):
        proc = subprocess.run(
            ["bash", str(HOOK)], input="this-is-not-json{{",
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "CLAUDE_SESSION_ID": f"test-{uuid.uuid4()}"})
        self.assertEqual(proc.returncode, 0)


class HookRespectsDisableEnvVar(_InstinctTestCase):
    def test_disable_env_var_skips_all_processing(self):
        session, log_path = self._paths()
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_INSTINCT_INJECTION": "1"},
                plugin_data=self.plugin_data)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists())
        finally:
            _cleanup(log_path)


if __name__ == "__main__":
    unittest.main()
