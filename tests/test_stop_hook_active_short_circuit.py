"""Wave 1 / Task A1: regression test for stop_hook_active short-circuit.

Every hook registered on Stop or SubagentStop in settings.json (excluding
external `hcom` entries and the inline `type: agent` Stop entry) MUST
short-circuit cleanly when fed {"stop_hook_active": true} on stdin:

  - exit 0
  - emit nothing on stdout (no context messages, no JSONL appended to stdout)
  - do not write any JSONL forensic file under $HOME/.claude/metrics
  - do not write any pipeline trajectory file under $HOME/.claude/pipeline-state

The contract is documented at https://code.claude.com/docs/en/hooks
("If your Stop hook calls claude recursively or spawns a subagent, that
nested call's Stop hooks will see stop_hook_active: true. Use this to skip
expensive operations or logging in nested calls.")

Without the guard, nested Stop firings duplicate trajectory rows, double-
fire auto-learn triggers, double-emit cost records, and — if any hook
ever returns decision:"block" — loop infinitely. See
knowledge/stop-hook-active-checklist.md for the full checklist.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"
SETTINGS_PATH = REPO_ROOT / "settings.json"

# Hooks excluded from the audit (external entries, not maintained in this repo,
# or non-shell entries that cannot be tested via stdin pipe).
EXTERNAL_PREFIXES = ("$HOME/.local/bin/hcom", "rtk hook")


def _resolve_hook_basenames(event: str) -> list[str]:
    """Return the basenames of in-repo shell hooks registered on `event`."""
    settings = json.loads(SETTINGS_PATH.read_text())
    groups = settings["hooks"].get(event, [])
    basenames: list[str] = []
    for group in groups:
        for entry in group.get("hooks", []):
            if entry.get("type") != "command":
                continue
            # Entries were hardened to the fail-safe `bash -lc '...'` wrapper
            # form (command='bash', script path inside args[1]). Scan the
            # joined command + args so the script name is still discoverable.
            text = " ".join([entry.get("command", "")] + entry.get("args", []))
            if any(prefix in text for prefix in EXTERNAL_PREFIXES):
                continue
            match = re.search(r"hooks/([A-Za-z0-9_.-]+\.sh)", text)
            if match:
                basenames.append(match.group(1))
    return basenames


def _hermetic_home() -> tempfile.TemporaryDirectory:
    """Create a tmpdir HOME the hook can write into without polluting real state.

    The `.claude` skeleton must exist because some hooks call `mkdir -p` only
    after passing the guard — but if a hook DOES write something through the
    guard, we want to detect it, so we deliberately keep all subdirs missing.
    """
    return tempfile.TemporaryDirectory()


class StopHookActiveShortCircuit(unittest.TestCase):
    maxDiff = None

    def test_inventory_matches_documented_set(self):
        # If this fails, a new Stop/SubagentStop hook landed without updating
        # the audit set below. Update both this set AND
        # knowledge/stop-hook-active-checklist.md.
        stop = set(_resolve_hook_basenames("Stop"))
        subagent_stop = set(_resolve_hook_basenames("SubagentStop"))
        self.assertEqual(stop, {
            "auto-pr.sh",
            "cost-tracker.sh",
            "auto-learn-gate.sh",
            "codebase-map-poll.sh",
            "stuck-guard.sh",
        })
        self.assertEqual(subagent_stop, {
            "subagent-validation.sh",
            "subagent-stop-trajectory.sh",
            "worktree-cwd-check.sh",
            "cost-feed.sh",
            "quality-gate-stop.sh",
            "tdd-guard-stop.sh",
            "bug-fixed-payload-validator.sh",
        })

    def test_every_stop_hook_short_circuits(self):
        for name in _resolve_hook_basenames("Stop"):
            with self.subTest(hook=name, event="Stop"):
                self._assert_short_circuit(name)

    def test_every_subagent_stop_hook_short_circuits(self):
        for name in _resolve_hook_basenames("SubagentStop"):
            with self.subTest(hook=name, event="SubagentStop"):
                self._assert_short_circuit(name)

    # Subdirectories under $HOME/.claude/ that ANY in-repo hook may write to
    # post-guard. If a hook regresses and writes to one of these under
    # stop_hook_active=true, the assertion below catches it. Sourced from a
    # full audit of `\$HOME/.claude/` write paths across every Stop and
    # SubagentStop hook (metrics, pipeline-state, learning, state — extend
    # this list when a new write surface is added to any hook).
    GUARDED_SIDE_EFFECT_DIRS = (
        "metrics",
        "pipeline-state",
        "learning",
        "state",
    )

    def _assert_short_circuit(self, hook_basename: str) -> None:
        with _hermetic_home() as home:
            home_path = Path(home)
            (home_path / ".claude").mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["HOME"] = home
            # Force standard profile so check_hook_profile gates do not mask
            # the test (some hooks fast-exit on minimal/empty profile, which
            # would render the assertion vacuous).
            env["CLAUDE_HOOK_PROFILE"] = "standard"
            # Prevent the hook from finding any active pipeline state — those
            # writes would happen post-guard, but we want the guard to be the
            # only reason side effects are absent.
            env.pop("CLAUDE_PIPELINE_TASK_ID", None)
            result = subprocess.run(
                ["bash", str(HOOKS_DIR / hook_basename)],
                input='{"stop_hook_active": true}\n',
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0,
                             f"{hook_basename} exited {result.returncode}: "
                             f"stderr={result.stderr!r}")
            self.assertEqual(result.stdout, "",
                             f"{hook_basename} emitted stdout: {result.stdout!r}")
            for sub in self.GUARDED_SIDE_EFFECT_DIRS:
                target = home_path / ".claude" / sub
                self.assertFalse(target.exists(),
                                 f"{hook_basename} wrote to {target} "
                                 f"(stop_hook_active guard missed)")


class TrapRegistrationOrdering(unittest.TestCase):
    """Static check: every Stop/SubagentStop hook registers its EXIT trap
    BEFORE the first early-exit. Mirrors the C8 instinct in session memory.

    Without this ordering, a trap registered after the first early-exit
    silently does not fire on that path — the hook stops emitting forensic
    records on the short-circuit branch, and the operator loses visibility.
    """

    def test_trap_registered_before_first_early_exit(self):
        for event in ("Stop", "SubagentStop"):
            for name in _resolve_hook_basenames(event):
                with self.subTest(hook=name, event=event):
                    body = (HOOKS_DIR / name).read_text()
                    trap_idx = self._first_module_scope_trap(body)
                    exit_idx = self._first_early_exit(body)
                    self.assertIsNotNone(trap_idx,
                                         f"{name} has no module-scope `trap` "
                                         "line — add `trap 'log_hook_event "
                                         "$?' EXIT` before any early exit "
                                         "(in-function traps do not satisfy "
                                         "this gate)")
                    self.assertIsNotNone(exit_idx,
                                         f"{name} has no early-exit line — "
                                         "expected at least the "
                                         "stop_hook_active short-circuit")
                    self.assertLess(trap_idx, exit_idx,
                                    f"{name}: trap at line {trap_idx} must "
                                    f"precede first early-exit at line "
                                    f"{exit_idx}")

    @staticmethod
    def _first_module_scope_trap(body: str) -> int | None:
        # Require the trap to start at column 0 (no leading whitespace) so an
        # in-function `trap '...' EXIT` does not satisfy the gate. Comments
        # are stripped before the match so a future `# trap ...` note does
        # not produce a false positive.
        for i, line in enumerate(body.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if re.match(r"^trap\s+", line):
                return i
        return None

    @staticmethod
    def _first_early_exit(body: str) -> int | None:
        # First line that can short-circuit the hook. Covers explicit
        # `exit 0`/`exit 1`, chained `&& exit` / `|| exit` (e.g. from a
        # sourced check_hook_profile guard), and `return 0`/`return 1`
        # from a sourced function. Comment lines are skipped so a stray
        # `# always exit 0` cannot trip the heuristic.
        patterns = (
            r"\bexit\s+[01]\b",
            r"\|\|\s*exit\b",
            r"&&\s*exit\b",
            r"\breturn\s+[01]\b",
        )
        for i, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in patterns:
                if re.search(pattern, stripped):
                    return i
        return None


if __name__ == "__main__":
    unittest.main()
