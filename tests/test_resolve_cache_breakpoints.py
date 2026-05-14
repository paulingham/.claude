"""Slice B AC-B4, AC-B5 — _lib/resolve-cache-breakpoints.py contract.

The Python resolver emits exactly 2 lines on stdout:
  line 1: decision token (`LOG` or `SKIP`)
  line 2: JSON payload with `anchors` array containing 4 entries:
    - rules-core-tail (status: advisory, ttl: 1h, segment_hash + byte_position)
    - persona-tail (status: deferred, reason: persona-marker-deferred)
    - protocol-tail (status: deferred, reason: protocol-splice-not-implemented)
    - tool-result-tail (status: deferred, reason: outside-hook-surface-v2.1.140)

The rules-core-tail segment_hash MUST be a stable SHA-256 over the byte stream
of $CLAUDE_CONFIG_DIR/rules/core.md.
"""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER = REPO_ROOT / "hooks" / "_lib" / "resolve-cache-breakpoints.py"

VALID_AGENT_INPUT = json.dumps({
    "tool_name": "Agent",
    "tool_input": {"subagent_type": "software-engineer", "prompt": "x"},
})

REQUIRED_DEFERRED = {
    "persona-tail": "persona-marker-deferred",
    "protocol-tail": "protocol-splice-not-implemented",
    "tool-result-tail": "outside-hook-surface-v2.1.140",
}


def _run_resolver(stdin: str, config_dir: Path):
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    proc = subprocess.run(
        ["python3", str(RESOLVER)],
        input=stdin, env=env, capture_output=True, text=True, timeout=5,
    )
    return proc.stdout, proc.returncode


def _fixture_config_dir(tmp: Path) -> Path:
    cfg = tmp / ".claude"
    (cfg / "rules").mkdir(parents=True)
    # Copy current rules/core.md into the fixture config dir so the resolver
    # has a real byte stream to hash.
    (cfg / "rules" / "core.md").write_bytes(
        (REPO_ROOT / "rules" / "core.md").read_bytes())
    return cfg


class ResolverEmitsTwoLineStdout(unittest.TestCase):
    def test_resolver_emits_two_line_stdout_with_anchors_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout, rc = _run_resolver(VALID_AGENT_INPUT, _fixture_config_dir(Path(tmp)))
        self.assertEqual(rc, 0, f"resolver exited non-zero: rc={rc}")
        lines = stdout.splitlines()
        self.assertEqual(
            len(lines), 2,
            f"resolver must emit exactly 2 lines (got {len(lines)}): {stdout!r}")
        self.assertEqual(
            lines[0], "LOG",
            f"line 1 (decision token) must equal 'LOG' for Agent input, got {lines[0]!r}")
        payload = json.loads(lines[1])
        self.assertIn("anchors", payload, "payload must contain `anchors` key")
        anchors = payload["anchors"]
        self.assertEqual(
            len(anchors), 4,
            f"payload must contain exactly 4 anchors (got {len(anchors)})")
        by_name = {a["name"]: a for a in anchors}
        # rules-core-tail: advisory + ttl: 1h + segment_hash + byte_position.
        rc_anchor = by_name.get("rules-core-tail")
        self.assertIsNotNone(rc_anchor, "rules-core-tail anchor missing")
        self.assertEqual(rc_anchor["status"], "advisory")
        self.assertEqual(rc_anchor["ttl"], "1h")
        self.assertRegex(
            rc_anchor["segment_hash"], r"^[0-9a-f]{64}$",
            "segment_hash must be hex SHA-256")
        self.assertIsInstance(rc_anchor["byte_position"], int)
        # The three deferred anchors with matching reason enums.
        for name, reason in REQUIRED_DEFERRED.items():
            self.assertIn(name, by_name, f"anchor {name} missing")
            self.assertEqual(by_name[name]["status"], "deferred",
                             f"{name} must be deferred")
            self.assertEqual(by_name[name]["reason"], reason,
                             f"{name} reason must be {reason}")


class RulesCoreTailHashIsStable(unittest.TestCase):
    def test_rules_core_tail_hash_is_stable_across_invocations_against_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _fixture_config_dir(Path(tmp))
            hashes = set()
            for _ in range(10):
                stdout, rc = _run_resolver(VALID_AGENT_INPUT, cfg)
                payload = json.loads(stdout.splitlines()[1])
                rc_anchor = next(a for a in payload["anchors"]
                                 if a["name"] == "rules-core-tail")
                hashes.add(rc_anchor["segment_hash"])
            self.assertEqual(
                len(hashes), 1,
                f"segment_hash must be identical across 10 invocations against "
                f"the same fixture file (got {len(hashes)} distinct values)")
            # Hash must equal a fresh SHA-256 of the fixture file.
            fixture_bytes = (cfg / "rules" / "core.md").read_bytes()
            expected = hashlib.sha256(fixture_bytes).hexdigest()
            self.assertEqual(
                hashes.pop(), expected,
                "segment_hash must match canonical SHA-256 of rules/core.md bytes")


class ResolverSkipsNonAgentInput(unittest.TestCase):
    def test_resolver_emits_skip_for_non_agent_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _fixture_config_dir(Path(tmp))
            stdout, rc = _run_resolver(
                json.dumps({"tool_name": "Skill", "tool_input": {}}), cfg)
        self.assertEqual(rc, 0)
        lines = stdout.splitlines()
        self.assertEqual(lines[0], "SKIP",
                         "non-Agent input must yield decision token SKIP")


if __name__ == "__main__":
    unittest.main()
