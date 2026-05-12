"""C8 S4: anti-pattern mining gate + recurrence-3 emission.

Tests `hooks/_lib/learn_anti_pattern_mining.py`, the Python module that
`/learn` Step 3d invokes. Mining gates on `phases.review.rounds >= 2`,
clusters flat-string `scratchpad_findings` by `(category, summary_normalised)`
across pipelines, and emits one anti-pattern instinct file per cluster
that recurs across >= 3 distinct pipelines.

All ACs use a shared `_make_pipeline_obs` builder for synthetic
observation records.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from learn_anti_pattern_mining import mine_anti_patterns  # noqa: E402


def _make_pipeline_obs(pipeline_id, rounds, scratchpad_findings):
    """Builder for a single synthetic pipeline observation record.

    Mirrors the production schema as documented in
    `protocols/autonomous-intelligence.md` § Observation Capture.
    `rounds=None` simulates a legacy record missing the
    `phases.review.rounds` field.
    """
    record = {
        "record_type": "pipeline",
        "pipeline_id": pipeline_id,
        "scratchpad_findings": scratchpad_findings,
    }
    if rounds is None:
        record["phases"] = {}
    else:
        record["phases"] = {"review": {"rounds": rounds}}
    return record


def _write_observations(tmp_path, records):
    """Write records to {tmp_path}/observations.jsonl (one per line)."""
    obs = tmp_path / "observations.jsonl"
    with obs.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return obs


def _emitted(tmp_path):
    """All anti-pattern files emitted into {tmp_path}/instincts/."""
    instincts_dir = tmp_path / "instincts"
    if not instincts_dir.exists():
        return []
    return sorted(instincts_dir.glob("anti-pattern-*.md"))


class MiningGateRoundsLessThan2NoEmission(unittest.TestCase):
    def test_rounds_1_observations_produce_no_antipattern_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: payment webhook timing flake"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=1,
                                   scratchpad_findings=findings)
                for n in range(5)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(_emitted(tmp_path), [])


class MiningRequiresThreeDistinctPipelines(unittest.TestCase):
    def test_third_recurrence_emits_first_and_second_do_not(self):
        import tempfile
        finding = ["warning: payment webhook timing"]
        # After ONE pipeline: zero.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs("pipe-1", rounds=2,
                                   scratchpad_findings=finding)])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(_emitted(tmp_path), [])
        # After TWO pipelines: zero.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs("pipe-1", rounds=2,
                                   scratchpad_findings=finding),
                _make_pipeline_obs("pipe-2", rounds=2,
                                   scratchpad_findings=finding),
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(_emitted(tmp_path), [])
        # After THREE pipelines: one anti-pattern at confidence=0.5.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            self.assertIn("confidence: 0.5", text)


class MiningConfidenceFormula(unittest.TestCase):
    def test_recurrence_5_yields_confidence_06(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Rewritten from "fragility:" → "warning:" under domain-weighted
            # floor (NEW-1): preserves original N=5 → 0.6 intent because
            # warning maps to workflow domain (floor=0.5) so 0.5 + 0.05*2 = 0.6.
            # Under fragility (architecture floor=0.7), N=5 would yield 0.8
            # and break this test's intent. The cap-test at N=20 below still
            # uses workflow and remains valid.
            finding = ["warning: config parser unchecked"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in range(5)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            self.assertIn("confidence: 0.6", files[0].read_text())


class MiningConfidenceCappedAt085(unittest.TestCase):
    def test_recurrence_20_yields_085_not_higher(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            finding = ["warning: long fixture rebuilds slow CI"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in range(20)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            self.assertIn("confidence: 0.85", files[0].read_text())


class MiningSkipsLegacyObservationsWithoutRoundsField(unittest.TestCase):
    def test_observations_missing_phases_review_rounds_key_skipped_not_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            finding = ["warning: legacy record absence"]
            # 4 legacy records (rounds=None) + 0 valid → must NOT emit
            # (legacy records are skipped, NOT coerced to rounds=0).
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"legacy-{n}", rounds=None,
                                   scratchpad_findings=finding)
                for n in range(4)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(_emitted(tmp_path), [])


class EmittedAntiPatternFrontmatterShape(unittest.TestCase):
    def test_emitted_file_has_category_anti_pattern_and_correct_roles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # `warning:` prefix → domain="workflow" per the lookup table
            finding = ["warning: shared id collisions across modules"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            self.assertIn("category: anti-pattern", text)
            self.assertIn("software-engineer", text)
            self.assertIn("frontend-engineer", text)
            self.assertIn("domain: workflow", text)


class EmittedAntiPatternBodyUnder200Chars(unittest.TestCase):
    def test_emitted_pattern_body_first_line_within_200_chars(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Long summary text — emitter must cap the rendered body at 200.
            long_text = "x" * 500
            finding = [f"warning: {long_text}"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            # Find the `## Pattern` body and confirm its first line is <=200.
            in_body = False
            first_line = None
            for line in text.splitlines():
                if line.startswith("## Pattern"):
                    in_body = True
                    continue
                if in_body and line.strip():
                    first_line = line
                    break
            self.assertIsNotNone(first_line)
            self.assertLessEqual(len(first_line), 200)


class EmittedFileLoadsThroughProductionLoaderPipeline(unittest.TestCase):
    """End-to-end check: a freshly-emitted anti-pattern file is loadable
    by `instinct_loader_helpers` (validate + normalize) and renders
    through `instinct_injector.resolve_for_agent` with the AVOID prefix.
    """

    def test_emitted_file_validates_normalizes_and_renders_with_avoid_prefix(
            self):
        import tempfile
        from instinct_loader_helpers import normalize, parse_file, validate
        from instinct_injector import resolve_for_agent

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            finding = ["warning: payment webhook timing"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in (1, 2, 3)
            ])
            files = mine_anti_patterns(observations_path=obs,
                                       instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(files), 1)
            fm, body = parse_file(files[0])
            self.assertIsNone(validate(fm, body))
            normalised = normalize(fm, body, "project")
            self.assertEqual(normalised["category"], "anti-pattern")
            out = resolve_for_agent("software-engineer", ["software-engineer"],
                                    [normalised], min_confidence=0.4)
            self.assertIn("AVOID:", out)


class MiningSilentlySkipsMalformedFindings(unittest.TestCase):
    """Risk-Register regression: a flat scratchpad finding lacking the
    `": "` separator is malformed (e.g. `"warning"` with no body, or
    `"some narration text"` written by a build agent that ignored the
    scratchpad format). `_parse_finding` returns None and the cluster
    is skipped. The mining loop MUST NOT crash, MUST NOT emit a
    cluster keyed off the malformed string, and MUST still emit the
    cluster for any well-formed sibling findings present in the same
    observation.
    """

    def test_malformed_finding_skipped_loop_continues_well_formed_emits(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Each pipeline carries TWO findings: one malformed (no
            # ": " separator), one well-formed. The malformed one MUST
            # be silently skipped; the well-formed one MUST still
            # trigger emission on the third pipeline.
            findings = ["malformed-no-separator-ever",
                        "warning: real signal here"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            # The mining call MUST NOT raise on the malformed entry.
            files = mine_anti_patterns(observations_path=obs,
                                       instincts_dir=tmp_path / "instincts")
            # Exactly one cluster — from the well-formed finding.
            # (Malformed findings are silently skipped, NOT clustered
            # under a synthetic key.)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            self.assertIn("real signal here", text)
            # And the malformed string did NOT leak into the file.
            self.assertNotIn("malformed-no-separator-ever", text)

    def test_only_malformed_findings_produces_zero_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 3 pipelines whose ONLY findings are malformed strings.
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=["just-narration",
                                                        "no colon present"])
                for n in (1, 2, 3)
            ])
            files = mine_anti_patterns(observations_path=obs,
                                       instincts_dir=tmp_path / "instincts")
            # Zero — no cluster has a real category key.
            self.assertEqual(files, [])


class MiningDomainFloorMap(unittest.TestCase):
    """AC1: `_DOMAIN_FLOOR` map exposes five domain→floor entries plus
    `_DEFAULT_FLOOR == 0.5`. Replaces the prior flat `_CONFIDENCE_FLOOR`."""

    def test_domain_floor_map_has_five_entries_plus_default(self):
        from learn_anti_pattern_mining import _DEFAULT_FLOOR, _DOMAIN_FLOOR
        self.assertEqual(_DOMAIN_FLOOR, {
            "workflow": 0.5,
            "testing": 0.6,
            "code-style": 0.6,
            "architecture": 0.7,
            "security": 0.7,
        })
        self.assertEqual(_DEFAULT_FLOOR, 0.5)


class MiningConfidenceForSignature(unittest.TestCase):
    """AC2: `_confidence_for(distinct_pipeline_count, domain)` resolves the
    domain-weighted floor and clamps to the uniform 0.85 cap. Unknown domain
    falls back to `_DEFAULT_FLOOR` (workflow floor)."""

    def test_confidence_for_returns_domain_resolved_floor_capped_at_085(self):
        from learn_anti_pattern_mining import _confidence_for
        # Workflow floor at threshold N=3 → 0.5 (no boost yet).
        self.assertEqual(_confidence_for(3, "workflow"), 0.5)
        # Architecture floor (0.7) reaches cap exactly at N=6:
        # 0.7 + 0.05 * (6 - 3) = 0.85.
        self.assertEqual(_confidence_for(6, "architecture"), 0.85)
        # Workflow at N=20 must still cap at 0.85 (cap monotonic).
        self.assertEqual(_confidence_for(20, "workflow"), 0.85)
        # Unknown domain → default floor (0.5) at threshold yields 0.5.
        self.assertEqual(_confidence_for(3, "unknown-domain"), 0.5)


class MiningRenderInstinctResolvesDomainBeforeConfidence(unittest.TestCase):
    """AC3: `_render_instinct` must resolve `domain` BEFORE computing
    confidence, because confidence depends on the floor for that domain.
    Joint observation of domain + confidence in the emitted file proves
    the call ordering — if domain were resolved AFTER, the confidence
    would still be the workflow-default value (0.5 at N=3) instead of
    the architecture-floor value (0.7 at N=3)."""

    def test_architecture_domain_at_n3_emits_confidence_07_proves_ordering(
            self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # `fragility:` prefix → architecture domain (floor 0.7).
            finding = ["fragility: cross-module shared state mutated"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}", rounds=2,
                                   scratchpad_findings=finding)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            self.assertIn("domain: architecture", text)
            self.assertIn("confidence: 0.7", text)


class MiningDomainWeightedFloors(unittest.TestCase):
    """AC5: end-to-end domain-weighted floor coverage via `mine_anti_patterns`.
    Each test asserts the emitted file's `confidence:` value for a chosen
    domain and recurrence count. Workflow caps at N=10, architecture at N=6.
    """

    def _emit_and_read(self, tmp_path, finding, pipeline_count):
        obs = _write_observations(tmp_path, [
            _make_pipeline_obs(f"pipe-{n}", rounds=2,
                               scratchpad_findings=finding)
            for n in range(pipeline_count)
        ])
        mine_anti_patterns(observations_path=obs,
                           instincts_dir=tmp_path / "instincts")
        files = _emitted(tmp_path)
        self.assertEqual(len(files), 1)
        return files[0].read_text()

    def test_workflow_n3_yields_confidence_05(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            text = self._emit_and_read(
                Path(tmp), ["warning: ci flake on slow fixture"], 3)
            self.assertIn("confidence: 0.5", text)
            self.assertIn("domain: workflow", text)

    def test_workflow_n10_caps_exactly_at_085(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # 0.5 + 0.05 * (10 - 3) = 0.85 exact cap.
            text = self._emit_and_read(
                Path(tmp), ["warning: workflow drift across pipelines"], 10)
            self.assertIn("confidence: 0.85", text)

    def test_workflow_n20_cap_holds_at_085(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Past-cap recurrence must NOT exceed 0.85 (cap is monotonic).
            text = self._emit_and_read(
                Path(tmp), ["warning: persistent workflow noise"], 20)
            self.assertIn("confidence: 0.85", text)

    def test_architecture_n3_yields_confidence_07(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            text = self._emit_and_read(
                Path(tmp), ["fragility: ports leak across modules"], 3)
            self.assertIn("confidence: 0.7", text)
            self.assertIn("domain: architecture", text)

    def test_architecture_n4_yields_confidence_075(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Mid-ramp: 0.7 + 0.05 * (4 - 3) = 0.75.
            text = self._emit_and_read(
                Path(tmp), ["fragility: contract drift in adapter"], 4)
            self.assertIn("confidence: 0.75", text)

    def test_architecture_n6_caps_exactly_at_085(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # 0.7 + 0.05 * (6 - 3) = 0.85 exact cap.
            text = self._emit_and_read(
                Path(tmp), ["fragility: shared singleton state"], 6)
            self.assertIn("confidence: 0.85", text)

    def test_unknown_domain_uses_default_floor_05(self):
        import tempfile
        # Direct call: an unknown domain string must yield the default floor.
        from learn_anti_pattern_mining import _confidence_for
        self.assertEqual(_confidence_for(3, "totally-made-up-domain"), 0.5)
        # End-to-end: a `pattern:` prefix maps via `_DOMAIN_BY_CATEGORY`
        # to "workflow" — which IS in `_DOMAIN_FLOOR`. To exercise the
        # `.get(domain, _DEFAULT_FLOOR)` fallback path through mining, we
        # rely on the direct call above (the production map currently has
        # no category whose resolved domain is absent from `_DOMAIN_FLOOR`,
        # which is itself a desirable invariant — every documented domain
        # has an explicit floor entry). The fallback exists for future
        # category additions whose domain may not yet have a floor entry.


if __name__ == "__main__":
    unittest.main()
