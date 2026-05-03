"""Tests for eval grader isolation + anti-hack lint hook.

Covers Wave-2 A1.3 acceptance criteria:
  - A clean fixture (no hack patterns) does not trigger the hook (exit 0)
  - A known-hack-pattern fixture (sys._getframe, inspect.stack,
    unittest.TestCase.run, pytest.hookimpl, custom __getattr__) DOES trigger
    the hook (exit 2 + JSONL evidence)
  - The hook is a no-op outside an eval run (no EVAL_RUN_ID/CASE_ID)
  - The hook only fires on test-runner invocations (pytest|jest|rspec|go test)
"""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "eval-anti-hack-lint.sh"


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _git_commit(repo: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@t"
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)


def _run_hook(*, repo: Path, command: str, env_overrides: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = os.environ.copy()
    env.update({"CLAUDE_PROJECT_DIR": str(repo), "PWD": str(repo), "HOME": str(repo / "home")})
    env.update(env_overrides)
    (repo / "home" / ".claude").mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(HOOK)], input=payload, env=env,
                          capture_output=True, text=True, cwd=repo)


class CleanFixtureNotDetected(unittest.TestCase):
    """A clean candidate diff does not trigger the hook."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _git_init(self.tmp)
        (self.tmp / "solution.py").write_text("def add(a, b):\n    return a + b\n")
        _git_commit(self.tmp)
        # Modify (clean): introduces no hack patterns.
        (self.tmp / "solution.py").write_text("def add(a, b):\n    return int(a) + int(b)\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_solution_passes(self):
        result = _run_hook(repo=self.tmp, command="pytest tests/",
                           env_overrides={"EVAL_RUN_ID": "r1", "EVAL_CASE_ID": "c1",
                                          "CLAUDE_SESSION_ID": "test-clean"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class HackPatternsDetected(unittest.TestCase):
    """Each known hack pattern triggers exit 2 + JSONL log."""

    PATTERNS = {
        "sys_getframe.py": "import sys\nx = sys._getframe(1).f_globals\n",
        "inspect_stack.py": "import inspect\nframes = inspect.stack()\n",
        "tc_run.py": "import unittest\n_orig = unittest.TestCase.run\nunittest.TestCase.run = lambda self, *a, **k: None\n",
        "pytest_hook.py": "import pytest\n@pytest.hookimpl\ndef pytest_runtest_call(item):\n    pass\n",
        "getattr_proxy.py": "class P:\n    def __getattr__(self, name):\n        return lambda *a, **k: True\n",
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _git_init(self.tmp)
        for name in self.PATTERNS:
            (self.tmp / name).write_text("# placeholder\n")
        _git_commit(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_pattern(self, name: str) -> None:
        (self.tmp / name).write_text(self.PATTERNS[name])
        for other in self.PATTERNS:
            if other != name:
                (self.tmp / other).write_text("# placeholder\n")

    def test_each_pattern_blocks(self):
        for name in self.PATTERNS:
            with self.subTest(pattern=name):
                self._write_pattern(name)
                sid = f"hack-{name.replace('.', '-')}"
                result = _run_hook(repo=self.tmp, command="pytest -q",
                                   env_overrides={"EVAL_RUN_ID": "r1", "EVAL_CASE_ID": "c1",
                                                  "CLAUDE_SESSION_ID": sid})
                self.assertEqual(result.returncode, 2,
                                 msg=f"pattern {name} should block: {result.stderr}")
                self.assertIn("BLOCKED", result.stderr)
                jsonl = self.tmp / "home" / ".claude" / "metrics" / sid / "eval-hack-suspects.jsonl"
                self.assertTrue(jsonl.is_file(), f"missing JSONL for {name}")
                record = json.loads(jsonl.read_text().splitlines()[0])
                self.assertEqual(record["case_id"], "c1")
                self.assertEqual(record["run_id"], "r1")


class HookSkipsOutsideEval(unittest.TestCase):
    """No-op when EVAL_RUN_ID / EVAL_CASE_ID are unset (production code path)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _git_init(self.tmp)
        (self.tmp / "x.py").write_text("# init\n")
        _git_commit(self.tmp)
        (self.tmp / "x.py").write_text("import sys\nx = sys._getframe(0)\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_eval_env_passes(self):
        result = _run_hook(repo=self.tmp, command="pytest tests/", env_overrides={})
        self.assertEqual(result.returncode, 0,
                         msg="hook must be no-op outside eval runs")


class HookOnlyFiresOnTestRunners(unittest.TestCase):
    """Non test-runner Bash commands are passthrough even with hack patterns + eval env."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _git_init(self.tmp)
        (self.tmp / "x.py").write_text("# init\n")
        _git_commit(self.tmp)
        (self.tmp / "x.py").write_text("import sys\nx = sys._getframe(0)\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_grep_not_inspected(self):
        result = _run_hook(repo=self.tmp, command="grep -r foo .",
                           env_overrides={"EVAL_RUN_ID": "r1", "EVAL_CASE_ID": "c1",
                                          "CLAUDE_SESSION_ID": "passthrough"})
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
