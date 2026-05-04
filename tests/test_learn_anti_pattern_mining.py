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
    `rules/_detail/autonomous-intelligence.md` § Observation Capture.
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
            finding = ["fragility: config parser unchecked"]
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


if __name__ == "__main__":
    unittest.main()
