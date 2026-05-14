"""Tests for the shared effective_floor() helper (slice-b AC6b).

The helper is the SINGLE source of truth for floor computation. Both
_resolved() (in resolve-instincts.py) and resolve_for_agent (when
floor_override is None) MUST call it.
"""
import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
sys.path.insert(0, _HOOKS_LIB)

from instinct_injector import effective_floor, resolve_for_agent  # noqa: E402


def _load_resolve_module():
    spec_path = Path(_HOOKS_LIB) / "resolve-instincts.py"
    spec = importlib.util.spec_from_file_location("_ri_floor", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_agent(tmp, name, min_conf, categories=None):
    cats_body = ""
    if categories is not None:
        cats_body = "instinct_categories: [" + ", ".join(categories) + "]\n"
    (Path(tmp) / f"{name}.md").write_text(
        f"---\nname: {name}\n{cats_body}min_confidence: {min_conf}\n---\nbody")


class HelperByteEqualityAcrossCallSites(unittest.TestCase):
    """Filter floor and log floor must be byte-equal for review-role."""

    def test_filter_and_log_floors_byte_equal_for_review_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "code-reviewer", "0.5", categories=["testing"])
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp},
                            clear=False):
                # Reload module so it picks up patched env-derived loaders.
                ri = _load_resolve_module()
                # Capture floor used by resolve_for_agent
                captured = {}
                real_resolve = ri.resolve_for_agent

                def spy_resolve(role, cats, instincts, **kwargs):
                    # When floor_override is None, helper is called inside.
                    # We verify equality via the helper directly.
                    captured["filter_floor"] = effective_floor(
                        "code-reviewer", dict(__import__("os").environ))
                    return real_resolve(role, cats, instincts, **kwargs)

                with mock.patch.object(ri, "resolve_for_agent",
                                       side_effect=spy_resolve), \
                     mock.patch.object(ri, "load_instincts", return_value=[]), \
                     mock.patch.object(ri, "project_hash", return_value="x"), \
                     mock.patch.object(ri, "write_log") as wl:
                    payload = {"tool_name": "Agent",
                               "tool_input": {"subagent_type": "code-reviewer"}}
                    ri._handle_agent_spawn(payload, "code-reviewer")
                log_floor = wl.call_args.args[2]["min_confidence"]
        self.assertEqual(captured["filter_floor"], log_floor)
        self.assertEqual(log_floor, 0.5)

    def test_effective_floor_helper_single_definition(self):
        """Exactly one `def effective_floor` lives under hooks/_lib/."""
        hits = []
        for p in Path(_HOOKS_LIB).glob("*.py"):
            for ln in p.read_text().splitlines():
                if re.match(r"\s*def effective_floor\b", ln):
                    hits.append(p.name)
        self.assertEqual(hits, ["instinct_injector.py"])


if __name__ == "__main__":
    unittest.main()
