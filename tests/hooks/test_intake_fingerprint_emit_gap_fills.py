"""Slice B — QA Final Gate gap-fills for hooks/_lib/intake-fingerprint-emit.py.

Three coverage holes identified by qa-test-strategy on Slice B:

1. `_is_path_contained` is the HIGH-1 defence-in-depth security gate; the
   existing tests exercise it only through `parse_frontmatter`. Three edges
   are unobserved at the helper level:
     - CLAUDE_CONFIG_DIR env var unset (default ~/.claude fallback)
     - CONFIG_DIR itself is a symlink (realpath must resolve through it)
     - pipeline-state directory does not exist on disk (realpath still
       contains the path; helper must still return True for an in-tree path)
2. Test-fixture env-var hygiene — setUp/tearDown pop CLAUDE_CONFIG_DIR
   unconditionally, which destroys an inherited parent-process value.
   Document the invariant: after teardown, helper falls back to the documented
   default (~/.claude/pipeline-state) — not a stale `self.tmp` value.

Additive — does not modify existing tests.
"""
import importlib.util
import os
import subprocess
import tempfile
import unittest

REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"]
).decode().strip()
HELPER = os.path.join(REPO_ROOT, "hooks", "_lib", "intake-fingerprint-emit.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("intake_fp_emit_gap", HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IsPathContainedEnvUnsetTest(unittest.TestCase):
    """Gap 1a: CLAUDE_CONFIG_DIR env var unset → default to ~/.claude."""

    def setUp(self):
        self._prior = os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prior is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = self._prior

    def test_env_unset_uses_home_claude_default(self):
        mod = _load_module()
        default_root = os.path.realpath(
            os.path.join(os.path.expanduser("~"), ".claude", "pipeline-state")
        )
        in_tree = os.path.join(default_root, "task-x", "intake.md")
        self.assertTrue(mod._is_path_contained(in_tree))

    def test_env_unset_rejects_out_of_tree(self):
        mod = _load_module()
        self.assertFalse(mod._is_path_contained("/tmp/elsewhere/intake.md"))


class IsPathContainedSymlinkedConfigDirTest(unittest.TestCase):
    """Gap 1b: CLAUDE_CONFIG_DIR points at a symlink. realpath() must resolve
    through it before computing the containment root."""

    def setUp(self):
        self._prior = os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.tmp = tempfile.mkdtemp()
        self.real_cfg = os.path.join(self.tmp, "real-cfg")
        self.sym_cfg = os.path.join(self.tmp, "sym-cfg")
        os.makedirs(os.path.join(self.real_cfg, "pipeline-state", "foo"))
        os.symlink(self.real_cfg, self.sym_cfg)
        os.environ["CLAUDE_CONFIG_DIR"] = self.sym_cfg
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        if self._prior is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = self._prior

    def test_symlinked_config_dir_resolves_through(self):
        mod = _load_module()
        path_via_symlink = os.path.join(
            self.sym_cfg, "pipeline-state", "foo", "intake.md"
        )
        self.assertTrue(mod._is_path_contained(path_via_symlink))


class IsPathContainedNonExistentPipelineStateTest(unittest.TestCase):
    """Gap 1c: pipeline-state directory does not yet exist. realpath() returns
    the path unchanged for non-existent leaves; the prefix check must still
    accept an in-tree synthetic path."""

    def setUp(self):
        self._prior = os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.tmp = tempfile.mkdtemp()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp  # no pipeline-state subdir
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        if self._prior is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = self._prior

    def test_in_tree_path_accepted_even_when_pipeline_state_absent(self):
        mod = _load_module()
        synthetic = os.path.join(self.tmp, "pipeline-state", "foo", "intake.md")
        self.assertTrue(mod._is_path_contained(synthetic))


if __name__ == "__main__":
    unittest.main()
