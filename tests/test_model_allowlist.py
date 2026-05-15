"""Slice A AC.4b — model allowlist audit.

Authored RED (Step 1). Implementation lives in ``hooks/_lib/model_allowlist.py``.
After Slice A migration, every agent frontmatter ``model:``/``executor:``/``advisor:``
must resolve to a member of ``model_allowlist._ALLOWED``.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import textwrap
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "_lib"))

import model_allowlist  # noqa: E402


class AllAgentFrontmatterInAllowlist(unittest.TestCase):
    """A.4b — every shipped agent frontmatter passes the allowlist check."""

    def test_all_agent_frontmatter_in_allowlist(self) -> None:
        errors = model_allowlist.check(_REPO_ROOT)
        self.assertEqual(errors, [], f"residual unknown-model tokens: {errors!r}")


class MissingAgentsDirReturnsSentinelError(unittest.TestCase):
    """MEDIUM-2 — repo without agents/ subdir surfaces a sentinel error token."""

    def test_missing_agents_dir_returns_sentinel_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            errors = model_allowlist.check(root)
            self.assertEqual(len(errors), 1, errors)
            self.assertTrue(errors[0].startswith("missing-agents-dir: "), errors[0])
            self.assertIn(str(root), errors[0])


class UnknownModelRejected(unittest.TestCase):
    """A.4b — synthetic offending frontmatter triggers the unknown-model token."""

    def test_unknown_model_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agents = root / "agents"
            agents.mkdir()
            target = agents / "fictional.md"
            target.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: fictional
                    model: claude-fictional-9-9
                    ---
                    body
                    """
                ),
                encoding="utf-8",
            )
            errors = model_allowlist.check(root)
            self.assertEqual(len(errors), 1, errors)
            self.assertTrue(errors[0].startswith("unknown-model: "), errors[0])
            self.assertIn("fictional.md", errors[0])


if __name__ == "__main__":
    unittest.main()
