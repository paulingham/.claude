"""AC4 — `/learn` mines recurring SANDBOX_FAILED divergences as fragility.

`hooks/_lib/learn_sandbox_fragility_mining.py` mirrors the existing
`learn_anti_pattern_mining.mine_anti_patterns` pattern:

- Iterate `observations.jsonl` line by line; skip blanks + malformed
  records (best-effort).
- Filter records via `sandbox_verify_observation.is_present` (NEVER
  coerce absence to a synthetic verdict).
- Keep records whose `phases.sandbox_verify.verdict == "SANDBOX_FAILED"`
  and harvest their `diverging_tests` list.
- Cluster by `sha1(test_name)[:8]` and emit one instinct file per
  cluster recurring across 3+ distinct pipelines.
- Confidence 0.5; roles `[software-engineer, sandbox-verify-engineer]`;
  domain `testing`; category `fragility`.

Tier-0 contract C5: returns `list[Path]`; malformed lines skipped not raised.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import learn_sandbox_fragility_mining
    return learn_sandbox_fragility_mining


def _make_sandbox_obs(pipeline_id, diverging_tests, verdict="SANDBOX_FAILED"):
    """Synthetic pipeline observation with a sandbox_verify block."""
    return {
        "record_type": "pipeline",
        "pipeline_id": pipeline_id,
        "phases": {"sandbox_verify": {
            "verdict": verdict,
            "rounds": 1,
            "cost_estimate_usd": 0.0,
            "divergence_count": len(diverging_tests),
            "diverging_tests": diverging_tests,
        }},
    }


def _write_observations(tmp_path, records):
    obs = tmp_path / "observations.jsonl"
    with obs.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return obs


def _emitted(tmp_path):
    instincts_dir = tmp_path / "instincts"
    if not instincts_dir.exists():
        return []
    return sorted(instincts_dir.glob("fragility-sandbox-*.md"))


class MineFragilityEmitsAt3Pipelines(unittest.TestCase):
    """3 pipelines with the same diverging test → one fragility instinct."""

    def test_3rd_recurrence_emits_one_instinct(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs(f"pipe-{n}",
                                  ["tests/test_x.py::test_flaky"])
                for n in range(3)
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(written), 1)
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            content = files[0].read_text()
            self.assertIn("category: fragility", content)
            self.assertIn("domain: testing", content)
            self.assertIn("confidence: 0.5", content)
            self.assertIn("sandbox-verify-engineer", content)
            self.assertIn("software-engineer", content)
            self.assertIn("tests/test_x.py::test_flaky", content)


class MineFragilityDoesNotEmitBelowThreshold(unittest.TestCase):
    """1-2 pipelines with the same divergence → no emission."""

    def test_2_pipelines_no_emit(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs("pipe-1", ["tests/x.py::t"]),
                _make_sandbox_obs("pipe-2", ["tests/x.py::t"]),
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(written, [])

    def test_1_pipeline_no_emit(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs("pipe-1", ["tests/x.py::t"]),
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(written, [])


class MineFragilityClustersByTestNameHash(unittest.TestCase):
    """Two distinct tests → two distinct clusters, each gated independently."""

    def test_distinct_tests_emit_distinct_files(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                # 3 pipelines flaking test_a
                _make_sandbox_obs("pipe-a-1", ["tests/test_a.py::t"]),
                _make_sandbox_obs("pipe-a-2", ["tests/test_a.py::t"]),
                _make_sandbox_obs("pipe-a-3", ["tests/test_a.py::t"]),
                # 3 pipelines flaking test_b
                _make_sandbox_obs("pipe-b-1", ["tests/test_b.py::u"]),
                _make_sandbox_obs("pipe-b-2", ["tests/test_b.py::u"]),
                _make_sandbox_obs("pipe-b-3", ["tests/test_b.py::u"]),
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(written), 2)
            bodies = [p.read_text() for p in _emitted(tmp_path)]
            joined = "\n".join(bodies)
            self.assertIn("tests/test_a.py::t", joined)
            self.assertIn("tests/test_b.py::u", joined)

    def test_filename_hash_is_deterministic(self):
        """Emitted filename embeds sha1(test_name)[:8] for stable identity."""
        mod = _load()
        import hashlib
        test_name = "tests/test_x.py::test_flaky"
        expected_hash = hashlib.sha1(
            test_name.encode("utf-8")).hexdigest()[:8]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs(f"pipe-{n}", [test_name])
                for n in range(3)
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(written), 1)
            self.assertIn(expected_hash, written[0].name)


class MineFragilitySkipsLegacyObservationsWithoutBlock(unittest.TestCase):
    """Legacy records without phases.sandbox_verify are skipped, not coerced."""

    def test_legacy_records_filtered(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 2 legacy (no sandbox_verify block) + 1 real → below threshold
            records = [
                {"record_type": "pipeline", "pipeline_id": "legacy-1"},
                {"record_type": "pipeline", "pipeline_id": "legacy-2"},
                _make_sandbox_obs("real-1", ["tests/x.py::t"]),
            ]
            obs = _write_observations(tmp_path, records)
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # Only 1 real pipeline → below recurrence threshold → no emit.
            self.assertEqual(written, [])

    def test_malformed_jsonl_lines_skipped_not_raised(self):
        """C5: malformed lines skipped, never raise (mirrors anti-pattern)."""
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = tmp_path / "observations.jsonl"
            # Mix of valid JSON and malformed lines + blanks.
            obs.write_text(
                json.dumps(_make_sandbox_obs("p1", ["tests/x.py::t"])) + "\n"
                "{ not valid json\n"
                "\n"  # blank
                + json.dumps(_make_sandbox_obs("p2", ["tests/x.py::t"])) + "\n"
                + json.dumps(_make_sandbox_obs("p3", ["tests/x.py::t"])) + "\n"
            )
            # Must not raise on the malformed line.
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # 3 valid records all clear → one emission.
            self.assertEqual(len(written), 1)

    def test_skipped_verdict_does_not_contribute(self):
        """Only SANDBOX_FAILED contributes; SKIPPED + VERIFIED do not."""
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs("p1", ["tests/x.py::t"],
                                  verdict="SANDBOX_VERIFIED"),
                _make_sandbox_obs("p2", ["tests/x.py::t"],
                                  verdict="SANDBOX_SKIPPED"),
                _make_sandbox_obs("p3", ["tests/x.py::t"],
                                  verdict="SANDBOX_FAILED"),
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # Only 1 SANDBOX_FAILED → below threshold.
            self.assertEqual(written, [])


class MineFragilityReturnsListOfPaths(unittest.TestCase):
    """C5: return type list[Path]."""

    def test_returns_list_of_paths(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = _write_observations(tmp_path, [
                _make_sandbox_obs(f"pipe-{n}", ["tests/x.py::t"])
                for n in range(3)
            ])
            written = mod.mine_sandbox_fragility(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertIsInstance(written, list)
            for item in written:
                self.assertIsInstance(item, Path)


if __name__ == "__main__":
    unittest.main()
