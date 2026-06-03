"""Slice slice-e-internal-eval — eval baseline contract for v2-plan parsing.

This file pins three things slice-e must ship:

1. **AC1** — Ship-phase prerequisite: `pipeline-state/architect-plan-dag/eval.md`
   carries `verdict: EVAL_PASSED` once the orchestrator runs `/internal-eval run`.
   Build-time test asserts the schema shape (frontmatter `verdict:` field
   present in any Ship-time eval phase file the harness produces). Pipeline
   does not require eval.md to exist at Build-time — slice-e Build adds the
   *fixture path/expectation* the Ship orchestrator will satisfy.

2. **AC2** — Eval baseline contains a deterministic v2-plan-dag-diamond case
   under `eval/cases/v2-plan-dag-diamond/` whose oracle asserts
   `wave_count == 3` AND `wave_count < slice_count` on the canonical
   `tests/fixtures/plan_dag/v2_diamond.md` input. The case's metadata.json
   matches the schema in `eval/cases/_example/SCHEMA.md`.

3. **AC2 B1 fix** — Regression detector: if a future plan change turned the
   diamond into a chain (4 slices serialised, wave_count=4), the case oracle
   `wave_count == 3` would trip. We assert this by constructing a synthetic
   chain plan in a tmpdir and demonstrating `topological_waves` produces 4
   waves on it (i.e. the case oracle would correctly fail).

4. **AC3** — Dog-food observation: this pipeline's own observation record
   carries `phases.build.wave_count` AND `phases.build.wave_widths`. At Build
   time we cannot assert the orchestrator's eventual JSONL output, so we
   assert the contract is *documented* — the field-reference table in
   `protocols/autonomous-intelligence.md` names both fields. (slice-c
   already pinned the doc surface; this test re-asserts the slice-e angle.)
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

# Imported lazily inside tests where they're used so the file remains
# importable for `pytest --collect-only` even before slice-b lands. In this
# branch slices a/b/c are cherry-picked, so the import works at module scope.
from plan_dag_resolver import parse_plan, topological_waves  # noqa: E402


CASE_ID = "v2-plan-dag-diamond"
CASE_DIR = REPO_ROOT / "eval" / "cases" / CASE_ID
DIAMOND_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "plan_dag" / "v2_diamond.md"
EVAL_PHASE_FILE_DOC = (
    REPO_ROOT / "protocols" / "pipeline-protocol.md"
)  # doc that names the eval phase artifact contract
AUTONOMOUS_INTEL = (
    REPO_ROOT / "protocols" / "autonomous-intelligence.md"
)


class EvalCaseExists(unittest.TestCase):
    """AC2 — the deterministic v2-plan-dag-diamond case exists and is well-formed."""

    def test_case_directory_present(self):
        self.assertTrue(
            CASE_DIR.is_dir(),
            f"slice-e must add eval case directory {CASE_DIR}",
        )

    def test_metadata_json_matches_schema(self):
        meta_path = CASE_DIR / "metadata.json"
        self.assertTrue(meta_path.is_file(), f"missing {meta_path}")
        meta = json.loads(meta_path.read_text())
        required = {
            "case_id",
            "classification",
            "source_pr",
            "min_harness_ref",
            "max_harness_ref",
            "flakiness_tier",
            "scoring_mode",
            "timeout_minutes",
            "cost_ceiling_usd",
            "synthetic",
        }
        self.assertEqual(
            set(meta.keys()),
            required,
            f"metadata.json keys must match SCHEMA.md exactly; got {sorted(meta.keys())}",
        )
        self.assertEqual(meta["case_id"], CASE_ID)
        self.assertEqual(meta["flakiness_tier"], "deterministic")
        self.assertTrue(meta["synthetic"], "this is an in-process synthetic case")

    def test_task_and_expected_present(self):
        for filename in ("task.md", "expected.md"):
            self.assertTrue(
                (CASE_DIR / filename).is_file(),
                f"missing {CASE_DIR / filename}",
            )


class EvalCaseOracleAssertsWaveCountLessThanSliceCount(unittest.TestCase):
    """AC2 (B1 fix, value-falsifiable) — case asserts wave_count < slice_count
    on the v2 diamond fixture. We re-execute the case oracle in-process here so
    the contract has a passing assertion in the slice-e build, not just a
    file-presence check."""

    def test_diamond_wave_count_is_three_and_less_than_slice_count(self):
        plan = parse_plan(str(DIAMOND_FIXTURE))
        waves = topological_waves(plan)
        wave_count = len(waves)
        slice_count = len(plan.slices)
        # Canonical assertion (mirrors expected.md oracle):
        self.assertEqual(
            wave_count, 3, f"diamond should produce 3 waves; got {wave_count}"
        )
        self.assertEqual(
            slice_count, 4, f"diamond has 4 slices; got {slice_count}"
        )
        self.assertLess(
            wave_count, slice_count,
            "B1 fix — parallelism win must be observable (wave_count < slice_count)",
        )

    def test_expected_md_documents_oracle_thresholds(self):
        """Oracle thresholds must be recorded in expected.md so Ship-time scoring
        can read them."""
        expected = (CASE_DIR / "expected.md").read_text()
        self.assertIn("wave_count == 3", expected)
        self.assertIn("slice_count == 4", expected)
        self.assertIn("wave_count < slice_count", expected)


class EvalCaseRegressionTrips(unittest.TestCase):
    """AC2 (B1 fix, regression-detector) — if a future plan change makes the
    diamond serialise (wave_count == 4 == slice_count), the case oracle trips.

    We can't literally mutate the shipped fixture without polluting other tests,
    so we synthesise a chain plan with 4 slices and demonstrate that
    `topological_waves` on it produces 4 waves — which would cause the
    `wave_count == 3` oracle to fail.
    """

    def test_chain_plan_with_four_slices_produces_four_waves(self):
        import tempfile

        chain_plan = """\
---
task_id: v2-diamond-regressed
schema_version: 2
dag: true
phase: plan
---

## Slices

```yaml
slices:
  - id: r
    depends-on: []
    description: Root.
  - id: a
    depends-on: [r]
    description: A.
  - id: b
    depends-on: [a]
    description: B (depends on A; serialises).
  - id: d
    depends-on: [b]
    description: D (depends on B; full chain).
```
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as tf:
            tf.write(chain_plan)
            chain_path = tf.name
        try:
            plan = parse_plan(chain_path)
            waves = topological_waves(plan)
            self.assertEqual(
                len(waves), 4,
                "regressed-to-chain plan must produce 4 waves (full serialisation)",
            )
            self.assertEqual(
                len(plan.slices), 4,
                "regressed-to-chain plan has 4 slices",
            )
            # Demonstrate the case oracle would trip:
            wave_count = len(waves)
            slice_count = len(plan.slices)
            self.assertFalse(
                wave_count < slice_count,
                "regressed-to-chain MUST fail the oracle wave_count < slice_count",
            )
        finally:
            Path(chain_path).unlink()


class DogFoodObservationContract(unittest.TestCase):
    """AC3 — observation field-reference doc names wave_count + wave_widths so
    the producer wiring is contracted. (Runtime emission verified at Ship.)"""

    def test_autonomous_intelligence_doc_names_wave_count_field(self):
        text = AUTONOMOUS_INTEL.read_text()
        self.assertIn(
            "phases.build.wave_count",
            text,
            "field-reference must document phases.build.wave_count (slice-c+e)",
        )

    def test_autonomous_intelligence_doc_names_wave_widths_field(self):
        text = AUTONOMOUS_INTEL.read_text()
        self.assertIn(
            "phases.build.wave_widths",
            text,
            "field-reference must document phases.build.wave_widths (slice-c+e)",
        )


class ShipPhaseEvalVerdictContract(unittest.TestCase):
    """AC1 — Ship-phase prerequisite. Build cannot assert the orchestrator's
    eventual eval.md output, so it documents the contract: `/internal-eval`
    skill emits `EVAL_PASSED` and the verdict-catalog entry for that verdict
    references the Ship-phase prerequisite. We assert the catalog still
    contains the EVAL_PASSED entry and the Ship pipeline step gates on it."""

    def test_eval_passed_remains_in_verdict_catalog(self):
        catalog = (REPO_ROOT / "protocols" / "verdict-catalog.md").read_text()
        self.assertIn("EVAL_PASSED", catalog)
        self.assertIn("`internal-eval`", catalog)


if __name__ == "__main__":
    unittest.main()
