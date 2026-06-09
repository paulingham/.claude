"""AC8b — runtime mutual-exclusivity guard for patch-critic mode tokens.

A patch-critic spawn prompt must contain at most ONE of:
- `Mode: tournament` (Slice 2 PDR-RTV)
- `Persona: <correctness|regression-risk|scope-creep>` (#93 multi-persona)

Spawns containing BOTH tokens are MODE_AMBIGUOUS — the orchestrator
surfaces this as PATCH_REJECTED and a forensic JSONL line is written
to `metrics/{session}/advisor-dispatch.jsonl` with `source:
"mode-ambiguous"`. Spawns containing NEITHER token are legacy
single-critic mode (preserves #93 default).

This test exercises the spawn-handling code path. Per architect's
scratchpad pattern note, the guard lives at
`hooks/_lib/mode_token_validator.py` (a pure-Python validator
invoked by the existing `pre-agent-advisor.sh` hook). The validator
is engine-agnostic and has no I/O of its own — the hook is responsible
for emitting the JSONL forensic line via `log-injection.sh`.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


class ModeTokenValidatorContract(unittest.TestCase):
    """Pure-validator contract — no I/O."""

    def setUp(self):
        # Fresh import each time so module-state cleanup is automatic.
        if "mode_token_validator" in sys.modules:
            del sys.modules["mode_token_validator"]
        import mode_token_validator
        self.mod = mode_token_validator

    # --- accepts_single_mode_token ----------------------------------------

    def test_accepts_tournament_only_prompt(self):
        prompt = "TaskId: foo\nMode: tournament\nCandidates: cand-a,cand-b"
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["mode"], "tournament")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tokens"], ["Mode: tournament"])

    def test_accepts_persona_only_prompt(self):
        prompt = "TaskId: foo\nPersona: correctness\nDiff: ..."
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["mode"], "persona")
        self.assertEqual(result["status"], "ok")
        self.assertIn("Persona: correctness", result["tokens"])

    def test_accepts_neither_token_as_legacy_single_critic(self):
        prompt = "TaskId: foo\nDiff: ..."
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["mode"], "single-critic")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tokens"], [])

    # --- rejects_dual_token_spawn -----------------------------------------

    def test_rejects_dual_token_spawn(self):
        prompt = ("TaskId: foo\n"
                  "Mode: tournament\n"
                  "Candidates: cand-a,cand-b\n"
                  "Persona: correctness\n")
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["mode"], "ambiguous")
        self.assertEqual(result["status"], "MODE_AMBIGUOUS")
        # Both offending tokens surface in the result for forensic logging.
        self.assertIn("Mode: tournament", result["tokens"])
        self.assertTrue(any(t.startswith("Persona:") for t in result["tokens"]),
                        f"expected a Persona: token in {result['tokens']}")


class ModeTokenValidatorPersonaSet(unittest.TestCase):
    """Persona token recognition is bounded to the documented enum."""

    def setUp(self):
        if "mode_token_validator" in sys.modules:
            del sys.modules["mode_token_validator"]
        import mode_token_validator
        self.mod = mode_token_validator

    def test_correctness_persona_recognised(self):
        self.assertEqual(self.mod.classify_mode("Persona: correctness")["mode"], "persona")

    def test_regression_risk_persona_recognised(self):
        self.assertEqual(self.mod.classify_mode("Persona: regression-risk")["mode"], "persona")

    def test_scope_creep_persona_recognised(self):
        self.assertEqual(self.mod.classify_mode("Persona: scope-creep")["mode"], "persona")

    def test_unknown_persona_not_treated_as_persona(self):
        # A `Persona:` line with an unknown value is NOT a valid persona token.
        # It falls through to single-critic mode (legacy behaviour preserved).
        result = self.mod.classify_mode("Persona: bogus")
        self.assertEqual(result["mode"], "single-critic")


class HookEmitsForensicJsonlOnAmbiguous(unittest.TestCase):
    """End-to-end: the hook detects ambiguity and writes a JSONL line.

    Exercises the bash entry point at `hooks/pre-agent-advisor.sh` with
    a synthesised payload containing both tokens. Asserts the forensic
    line appears in `metrics/{session}/advisor-dispatch.jsonl` with
    `source: "mode-ambiguous"` and the offending token list.
    """

    def setUp(self):
        self.tmp_metrics = tempfile.TemporaryDirectory()
        self.session = "test-mode-exclusivity-session"
        self.env = {
            "HOME": self.tmp_metrics.name,
            "CLAUDE_SESSION_ID": self.session,
            "PATH": os.environ["PATH"],
            "CLAUDE_HOOK_PROFILE": "standard",
            # GP-P1-01: force the resolver python path (default-OFF short-circuit).
            "CLAUDE_AGENT_INJECTION_FORCE": "1",
        }
        # Mirror $HOME → metrics dir layout.
        Path(self.tmp_metrics.name, ".claude", "metrics", self.session).mkdir(
            parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_metrics.cleanup()

    def _run_hook(self, payload):
        import subprocess
        hook_path = REPO_ROOT / "hooks" / "pre-agent-advisor.sh"
        completed = subprocess.run(
            ["bash", str(hook_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env,
            timeout=10,
        )
        return completed

    def _read_jsonl(self):
        path = Path(self.tmp_metrics.name, ".claude", "metrics",
                    self.session, "advisor-dispatch.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_ambiguous_spawn_writes_forensic_jsonl(self):
        payload = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "patch-critic",
                "prompt": ("TaskId: pdr-rtv-skill\n"
                           "Mode: tournament\n"
                           "Candidates: cand-a,cand-b\n"
                           "Persona: correctness\n"),
            },
        }
        result = self._run_hook(payload)
        self.assertEqual(result.returncode, 0,
                         f"hook should exit 0 (Path-B advisory); stderr={result.stderr}")

        records = self._read_jsonl()
        # Find the mode-ambiguous record (advisor-pairing record may also fire).
        ambig_records = [r for r in records if r.get("source") == "mode-ambiguous"]
        self.assertEqual(len(ambig_records), 1,
                         f"expected exactly 1 mode-ambiguous record; got {records}")

        rec = ambig_records[0]
        self.assertEqual(rec["agent_role"], "patch-critic")
        self.assertEqual(rec["resolved"]["status"], "MODE_AMBIGUOUS")
        # Token list MUST contain both offending tokens.
        token_str = "\n".join(rec["resolved"]["tokens"])
        self.assertIn("Mode: tournament", token_str)
        self.assertIn("Persona: correctness", token_str)

    def test_single_mode_spawn_writes_no_mode_ambiguous_record(self):
        payload = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "patch-critic",
                "prompt": "TaskId: foo\nMode: tournament\nCandidates: cand-a,cand-b",
            },
        }
        result = self._run_hook(payload)
        self.assertEqual(result.returncode, 0)
        records = self._read_jsonl()
        ambig = [r for r in records if r.get("source") == "mode-ambiguous"]
        self.assertEqual(len(ambig), 0,
                         f"single-mode spawn must not emit mode-ambiguous; got {records}")


class ModeTokenValidatorAdversarial(unittest.TestCase):
    """Adversarial probes — boundary, malformed input, error path coverage."""

    def setUp(self):
        if "mode_token_validator" in sys.modules:
            del sys.modules["mode_token_validator"]
        import mode_token_validator
        self.mod = mode_token_validator

    def test_none_prompt_classified_as_single_critic(self):
        # Null/empty: None prompt should not raise; treated as empty.
        result = self.mod.classify_mode(None)
        self.assertEqual(result["mode"], "single-critic")

    def test_token_inside_prose_not_matched(self):
        # Malformed input: mention of "Mode: tournament" in prose (not at line
        # start) should NOT activate tournament mode. Anchored regex required.
        result = self.mod.classify_mode("the user wrote Mode: tournament in their note")
        self.assertEqual(result["mode"], "single-critic",
                         "tokens must be matched at start of line, not mid-line")

    def test_unknown_persona_first_then_known_persona_still_classified(self):
        # Error-path: unknown persona BEFORE a known one should not block
        # detection of the known one (loop semantics, not first-match).
        prompt = "Persona: bogus\nPersona: correctness\n"
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["mode"], "persona",
                         "documented persona must surface even when an "
                         "unknown persona appears earlier in the prompt")

    def test_dual_persona_tokens_with_tournament_remain_ambiguous(self):
        # Boundary: multiple Persona: tokens AND a Mode: tournament token
        # should still flag ambiguity — finding ANY persona alongside
        # tournament is enough.
        prompt = ("Mode: tournament\n"
                  "Persona: correctness\n"
                  "Persona: scope-creep\n")
        result = self.mod.classify_mode(prompt)
        self.assertEqual(result["status"], "MODE_AMBIGUOUS")


if __name__ == "__main__":
    unittest.main()
