"""Consent gate for privileged installs (H1 security finding).

Sudo invocations (currently only Linux apt-get) MUST NOT run without
explicit user consent. Four pathways:
  1. TTY + user types y/yes           -> proceed
  2. TTY + user types anything else   -> abort (return 1, no subprocess)
  3. CLAUDE_BOOTSTRAP_CONSENT=1       -> proceed (CI/Cloud bypass)
  4. Non-TTY + env var unset          -> abort (return 1, no subprocess)
"""
import io
import os
import subprocess as sp
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap_steps  # noqa: E402


def _linux_patches():
    return (patch("embedder._lib.bootstrap_install.platform.system",
                  return_value="Linux"),
            patch("embedder._lib.bootstrap_steps.shutil.which",
                  return_value="/usr/bin/apt-get"))


class ConsentGateTtyAcceptsYes(unittest.TestCase):
    def test_tty_yes_proceeds_to_subprocess(self):
        ok = sp.CompletedProcess(args=[], returncode=0)
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_BOOTSTRAP_CONSENT"}
        linux, which = _linux_patches()
        with linux, which, \
             patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_steps.sys.stdin.isatty",
                   return_value=True), \
             patch("builtins.input", return_value="y"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=ok) as sub:
            code = bootstrap_steps.install_ort()
        self.assertEqual(code, 0)
        sub.assert_called_once()


class ConsentGateTtyRejectsEmpty(unittest.TestCase):
    def test_tty_empty_answer_aborts_without_subprocess(self):
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_BOOTSTRAP_CONSENT"}
        buf = io.StringIO()
        linux, which = _linux_patches()
        with linux, which, \
             patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_steps.sys.stdin.isatty",
                   return_value=True), \
             patch("builtins.input", return_value=""), \
             patch("embedder._lib.bootstrap_steps.subprocess.run") as sub:
            with redirect_stdout(buf):
                code = bootstrap_steps.install_ort()
        self.assertEqual(code, 1)
        sub.assert_not_called()
        self.assertIn("WARN", buf.getvalue())


class ConsentGateTtyRejectsOther(unittest.TestCase):
    def test_tty_non_yes_answer_aborts(self):
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_BOOTSTRAP_CONSENT"}
        linux, which = _linux_patches()
        with linux, which, \
             patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_steps.sys.stdin.isatty",
                   return_value=True), \
             patch("builtins.input", return_value="nope"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run") as sub:
            with redirect_stdout(io.StringIO()):
                code = bootstrap_steps.install_ort()
        self.assertEqual(code, 1)
        sub.assert_not_called()


class ConsentGateEnvVarBypassesPrompt(unittest.TestCase):
    def test_env_var_proceeds_without_prompt(self):
        ok = sp.CompletedProcess(args=[], returncode=0)
        linux, which = _linux_patches()
        with linux, which, \
             patch.dict(os.environ,
                        {"CLAUDE_BOOTSTRAP_CONSENT": "1"}, clear=False), \
             patch("builtins.input", side_effect=AssertionError(
                 "input() must not be called when env var set")), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=ok) as sub:
            code = bootstrap_steps.install_ort()
        self.assertEqual(code, 0)
        sub.assert_called_once()


class ConsentGateNonTtyAbortsWithoutEnvVar(unittest.TestCase):
    def test_non_tty_without_env_var_aborts_with_hint(self):
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_BOOTSTRAP_CONSENT"}
        buf = io.StringIO()
        linux, which = _linux_patches()
        with linux, which, \
             patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_steps.sys.stdin.isatty",
                   return_value=False), \
             patch("embedder._lib.bootstrap_steps.subprocess.run") as sub:
            with redirect_stdout(buf):
                code = bootstrap_steps.install_ort()
        self.assertEqual(code, 1)
        sub.assert_not_called()
        self.assertIn("CLAUDE_BOOTSTRAP_CONSENT", buf.getvalue())


class ConsentGateSkippedForBrew(unittest.TestCase):
    """Brew does not escalate — no consent required."""
    def test_macos_brew_install_proceeds_without_consent(self):
        ok = sp.CompletedProcess(args=[], returncode=0)
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_BOOTSTRAP_CONSENT"}
        with patch("embedder._lib.bootstrap_install.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/opt/homebrew/bin/brew"), \
             patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_steps.sys.stdin.isatty",
                   return_value=False), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=ok) as sub:
            code = bootstrap_steps.install_ort()
        self.assertEqual(code, 0)
        sub.assert_called_once()


if __name__ == "__main__":
    unittest.main()
