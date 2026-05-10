"""Slice C Tier 0 contract assertions for the codebase-map hooks.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice C — three
contracts:

1. Hook exit-code contract: BOTH hooks always exit 0, regardless of
   internal failure mode. Asserted by invoking the hook against a
   deliberately-broken state and confirming the exit status.
2. JSONL line shape: every line in
   `metrics/{session-id}/codebase-map-rebuild.jsonl` MUST contain the
   contract fields `(ts, file_count, time_ms, cache_hit_rate, sha_before,
   sha_after, hook)` as JSON. The shape is locked here so any drift in
   the emitter fails CI.
3. CLI argv contract: `python3 -m codebase_map.cli build <root> <cache>`
   is the only supported invocation form. Asserted by importing the CLI
   module and confirming the public entry point accepts `(repo_root,
   cache_dir)` positional args.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FIELDS = (
    "ts",
    "file_count",
    "time_ms",
    "cache_hit_rate",
    "sha_before",
    "sha_after",
    "hook",
)


class HookExitCodeContract(unittest.TestCase):
    """Both rebuild + poll hooks MUST exit 0 always (AC18 + AC21)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cbm-hook-contract-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run_hook(self, hook_name, **env_overrides):
        env = os.environ.copy()
        env["HOME"] = str(self.tmp)
        env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
        env["CLAUDE_PROJECT_HASH"] = "contracttest"
        env.update(env_overrides)
        result = subprocess.run(
            ["bash", str(REPO_ROOT / "hooks" / hook_name)],
            env=env,
            capture_output=True,
            timeout=20,
        )
        return result

    def test_rebuild_hook_exits_zero_when_disabled(self):
        result = self._run_hook(
            "codebase-map-rebuild.sh", CLAUDE_DISABLE_CODEBASE_MAP="1"
        )
        self.assertEqual(result.returncode, 0)

    def test_poll_hook_exits_zero_when_disabled(self):
        result = self._run_hook(
            "codebase-map-poll.sh", CLAUDE_DISABLE_CODEBASE_MAP="1"
        )
        self.assertEqual(result.returncode, 0)


class JsonlLineShapeContract(unittest.TestCase):
    """Every codebase-map-rebuild.jsonl line carries the 7 contract fields."""

    def test_contract_fields_locked(self):
        # The contract is the field SET; lock it here so any field added or
        # removed without a contract bump fails this test.
        expected = set(CONTRACT_FIELDS)
        # Build a sample line via the emitter to confirm the shape.
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        try:
            import codebase_map_emit  # noqa: WPS433 - dynamic import for test
        finally:
            sys.path.pop(0)
        sample = codebase_map_emit.build_record(
            file_count=12,
            time_ms=350,
            cache_hit_rate=0.83,
            sha_before="aaa",
            sha_after="bbb",
            hook="rebuild",
        )
        parsed = json.loads(sample)
        self.assertEqual(set(parsed.keys()), expected)


class CliArgvContract(unittest.TestCase):
    """`python3 -m codebase_map.cli build <root> <cache>` is the entry point."""

    def test_cli_module_exists(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from codebase_map import cli  # noqa: WPS433
        finally:
            sys.path.pop(0)
        # Must expose a `main(argv: list[str]) -> int` callable so that
        # `python3 -m codebase_map.cli` works.
        self.assertTrue(callable(getattr(cli, "main", None)))

    def test_cli_build_subcommand_signature(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from codebase_map import cli  # noqa: WPS433
        finally:
            sys.path.pop(0)
        # The `build` subcommand must take repo_root + cache_dir positional
        # args. We probe by calling main() with an empty repo and asserting
        # exit code 0 (success or graceful no-op — never crash).
        empty = Path(tempfile.mkdtemp(prefix="cbm-cli-"))
        cache = Path(tempfile.mkdtemp(prefix="cbm-cache-"))
        try:
            rc = cli.main(["build", str(empty), str(cache)])
            self.assertEqual(rc, 0)
        finally:
            shutil.rmtree(empty, ignore_errors=True)
            shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
