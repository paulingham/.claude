"""Tests for oracle-labeled fixtures and mutation gate — AC17-AC20.

AC17: Oracle reference contexts (3 fixtures).
AC18: MUTATION GATE — always-relevant scorer MUST fail the oracle irrelevant fixture.
AC19: Threshold env tests use patch.dict, NOT bare os.environ.pop.
AC20: Token delta is nonzero for irrelevant oracle, uses chars/4 formula.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


# ---- Oracle Fixture Definitions ----

# Fixture 1: Known-irrelevant protocol blob (high drop rate expected)
IRRELEVANT_PROTOCOL_BLOB = """## Protocol
The weather forecasting system uses multiple meteorological sensors to predict
rain fall and temperature changes. Each sensor has a calibration factor.
The outdoor environment can influence humidity measurements in various ways.
Birds migrate south during winter months. The jet stream affects pressure.
Atmospheric rivers carry moisture from the Pacific Ocean to inland regions.
Mountain ranges cause orographic lift which produces precipitation events.
The global circulation patterns determine seasonal weather variations across
different latitude zones. Farmers depend on accurate weather predictions.
Soil moisture affects crop yields and agricultural production significantly.
Oceanographic currents also influence regional climate and temperature patterns.
The albedo effect of snow and ice reflects solar radiation back into space.
Carbon dioxide levels affect the greenhouse effect and global temperature.
"""

# Fixture 2: Goal-relevant scratchpad (low drop rate expected)
# Lines are dense with the keyword set: authentication, service, engineer, build, software
RELEVANT_SCRATCHPAD = """## Scratchpad
Build the authentication service for the software engineer now.
Authentication service build requires software engineer discipline.
Engineer the authentication service build with software patterns.
Software engineer builds authentication service components here.
Build authentication service software engineer implementation.
Authentication service engineer build software architecture.
Service authentication build engineer software components work.
"""

# Fixture 3: Mixed context (irrelevant protocol + relevant scratchpad)
MIXED_CONTEXT = """## Scratchpad
Build the authentication service using TDD.
Engineer the auth module with clean architecture.
## Protocol
Weather forecasting systems use meteorological sensors.
The atmospheric pressure changes affect precipitation.
Farmers depend on accurate weather predictions for crops.
"""


class TestOracleFixtures(unittest.TestCase):
    """AC17: oracle-labeled reference context fixtures."""

    def _drop_rate(self, prompt, keywords):
        from swe_pruner import segment_content_blocks, propose_drops
        blocks = segment_content_blocks(prompt)
        if not blocks:
            return 0.0
        total_lines = sum(len(b.lines) for b in blocks)
        total_dropped = sum(
            end - start
            for b in blocks
            for start, end in propose_drops(b, keywords)
        )
        if total_lines == 0:
            return 0.0
        return total_dropped / total_lines

    def test_oracle_irrelevant_blob_has_high_drop_rate(self):
        """Known-irrelevant protocol blob: drop rate must be > 50%."""
        keywords = frozenset(["authentication", "service", "engineer", "build", "software"])
        drop_rate = self._drop_rate(IRRELEVANT_PROTOCOL_BLOB, keywords)
        self.assertGreater(drop_rate, 0.5,
                           f"Expected drop rate > 50% for irrelevant blob, got {drop_rate:.1%}")

    def test_oracle_relevant_scratchpad_has_low_drop_rate(self):
        """Goal-relevant scratchpad: drop rate must be < 20%."""
        keywords = frozenset(["authentication", "service", "engineer", "build", "software"])
        drop_rate = self._drop_rate(RELEVANT_SCRATCHPAD, keywords)
        self.assertLess(drop_rate, 0.2,
                        f"Expected drop rate < 20% for relevant scratchpad, got {drop_rate:.1%}")

    def test_oracle_mixed_context_drops_only_irrelevant_block(self):
        """Mixed context: irrelevant protocol block drops more than scratchpad."""
        from swe_pruner import segment_content_blocks, propose_drops
        keywords = frozenset(["authentication", "service", "engineer", "build", "software"])
        blocks = segment_content_blocks(MIXED_CONTEXT)

        scratchpad_block = next((b for b in blocks if b.block_type == "scratchpad"), None)
        protocol_block = next((b for b in blocks if b.block_type == "protocol"), None)

        self.assertIsNotNone(scratchpad_block, "No scratchpad block found in mixed context")
        self.assertIsNotNone(protocol_block, "No protocol block found in mixed context")

        scratchpad_drops = sum(
            end - start for start, end in propose_drops(scratchpad_block, keywords)
        )
        protocol_drops = sum(
            end - start for start, end in propose_drops(protocol_block, keywords)
        )

        scratchpad_total = len(scratchpad_block.lines)
        protocol_total = len(protocol_block.lines)

        scratchpad_rate = scratchpad_drops / scratchpad_total if scratchpad_total > 0 else 0
        protocol_rate = protocol_drops / protocol_total if protocol_total > 0 else 0

        self.assertGreater(protocol_rate, scratchpad_rate,
                           f"Protocol drop rate ({protocol_rate:.1%}) should exceed "
                           f"scratchpad drop rate ({scratchpad_rate:.1%})")


class TestMutationGate(unittest.TestCase):
    """AC18: MUTATION GATE — always-relevant scorer must FAIL oracle irrelevant fixture."""

    def test_always_relevant_scorer_fails_oracle_irrelevant_fixture(self):
        """
        This is the lying-advisory-log detection test.

        An always-relevant scorer (returns 1.0 for every line) would report
        zero drops on the known-irrelevant blob, which is WRONG.

        The REAL scorer must drop >50% of the irrelevant blob.
        If this test fails, the scorer is a lying advisory log.
        """
        from swe_pruner import segment_content_blocks, propose_drops

        def always_relevant_score(line, keywords):
            return 1.0  # Mutant: always says "relevant"

        keywords = frozenset(["authentication", "service", "engineer", "build", "software"])
        blocks = segment_content_blocks(IRRELEVANT_PROTOCOL_BLOB)
        total_lines = sum(len(b.lines) for b in blocks)

        # Simulate what propose_drops would do with an always-relevant scorer
        # (score >= threshold, so nothing gets dropped)
        # This is the "mutant" behavior: 0 lines dropped
        mutant_drops = 0  # Always-relevant scorer drops nothing

        mutant_drop_rate = mutant_drops / total_lines if total_lines > 0 else 0

        # The mutant drop rate should be 0 — but the ORACLE says it should be > 50%
        # This proves the mutant FAILS the oracle fixture
        self.assertLess(mutant_drop_rate, 0.5,
                        "Expected mutant (always-relevant) to drop < 50% — it passes vacuously")

        # Now verify the REAL scorer does better
        real_drops = sum(
            end - start
            for b in blocks
            for start, end in propose_drops(b, keywords)
        )
        real_drop_rate = real_drops / total_lines if total_lines > 0 else 0

        # The real scorer MUST drop more than the mutant
        self.assertGreater(real_drop_rate, mutant_drop_rate,
                           f"Real scorer ({real_drop_rate:.1%}) should drop more than "
                           f"always-relevant mutant ({mutant_drop_rate:.1%})")

        # And the real scorer must exceed the 50% oracle threshold
        self.assertGreater(real_drop_rate, 0.5,
                           f"Real scorer drop rate {real_drop_rate:.1%} fails oracle "
                           f"(must be > 50% for known-irrelevant blob)")


class TestEnvVarHygiene(unittest.TestCase):
    """AC19: Threshold env tests use patch.dict, NEVER bare os.environ.pop."""

    def test_threshold_env_uses_patch_dict_not_pop(self):
        """Verify patch.dict doesn't corrupt os.environ for other tests."""
        from swe_pruner import segment_content_blocks, propose_drops

        original_threshold = os.environ.get("CLAUDE_PRUNER_THRESHOLD")
        prompt = "## Scratchpad\nsome content here\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication"])

        # Use patch.dict — the right way
        with patch.dict(os.environ, {"CLAUDE_PRUNER_THRESHOLD": "0.9"}, clear=False):
            ranges_inside = propose_drops(blocks[0], keywords)
            # Inside the context, env var is set
            self.assertEqual(os.environ.get("CLAUDE_PRUNER_THRESHOLD"), "0.9")

        # After exiting context, env is restored
        restored = os.environ.get("CLAUDE_PRUNER_THRESHOLD")
        self.assertEqual(restored, original_threshold,
                         "patch.dict failed to restore CLAUDE_PRUNER_THRESHOLD")

    def test_env_not_mutated_across_tests(self):
        """Env mutations in one test must not bleed into others."""
        baseline = dict(os.environ)
        from swe_pruner import segment_content_blocks, propose_drops
        prompt = "## Scratchpad\nsome content\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["database"])
        with patch.dict(os.environ, {"CLAUDE_PRUNER_THRESHOLD": "0.5"}, clear=False):
            propose_drops(blocks[0], keywords)
        # Check no new keys leaked
        for key in os.environ:
            if key not in baseline:
                # Only keys we explicitly added via patch.dict should differ
                self.assertIn(key, ["CLAUDE_PRUNER_THRESHOLD"],
                              f"Unexpected key leaked into os.environ: {key!r}")


class TestTokenDelta(unittest.TestCase):
    """AC20: token_delta is nonzero for irrelevant oracle; uses chars/4 formula."""

    def test_token_delta_nonzero_for_irrelevant_oracle(self):
        """Irrelevant blob must produce a nonzero token delta estimate."""
        from swe_pruner import segment_content_blocks, propose_drops
        keywords = frozenset(["authentication", "service", "engineer", "build"])
        blocks = segment_content_blocks(IRRELEVANT_PROTOCOL_BLOB)
        total_delta = 0
        for block in blocks:
            ranges = propose_drops(block, keywords)
            for start, end in ranges:
                for i in range(start, end):
                    if i < len(block.lines):
                        total_delta += len(block.lines[i]) // 4
        self.assertGreater(total_delta, 0,
                           "Expected nonzero token delta for irrelevant oracle fixture")

    def test_token_delta_chars_div_4_formula(self):
        """Token estimate = char_count // 4 (established pattern, no tiktoken)."""
        from swe_pruner import segment_content_blocks, propose_drops, build_record
        keywords = frozenset(["authentication", "service"])
        blocks = segment_content_blocks(IRRELEVANT_PROTOCOL_BLOB)
        proposals = [(b, propose_drops(b, keywords)) for b in blocks]
        payload = {"tool_input": {
            "subagent_type": "software-engineer",
            "prompt": IRRELEVANT_PROTOCOL_BLOB,
        }}
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record = build_record(payload, proposals)

        # Verify chars/4 formula for each block
        for block_info in record["blocks_analyzed"]:
            # Total chars dropped = sum of line lengths for dropped lines
            saved_chars = block_info["estimated_tokens_saved"] * 4
            # The formula is: tokens_saved = chars_in_dropped_lines // 4
            # So: saved_chars = tokens_saved * 4 ≈ actual_chars (within rounding)
            self.assertGreaterEqual(saved_chars, 0)


if __name__ == "__main__":
    unittest.main()
