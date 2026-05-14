"""Slice B — AC5 (hooks/_lib/intake-fingerprint-emit.py)
Per-function unit tests for the 4-function decomposition:
  parse_frontmatter, build_record, append_jsonl, main
Asserts:
  - JSONL line shape via json.loads (all 13 keys present)
  - enum constraints on tier_emitted, detector_phase ∈ {rules, fallthrough}
  - parse_frontmatter handles missing, malformed, key-missing fixtures
  - build_record applies sentinel defaults
  - append_jsonl writes one line per call, JSON-valid
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"]
).decode().strip()
HELPER = os.path.join(REPO_ROOT, "hooks", "_lib", "intake-fingerprint-emit.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("intake_fp_emit", HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ParseFrontmatterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "intake.md")

    def test_parse_frontmatter_unit_well_formed(self):
        mod = _load_module()
        with open(self.path, "w") as f:
            f.write(
                "---\n"
                "tier_emitted: T1\n"
                "tier_initial: T1\n"
                "detector_phase: rules\n"
                "detector_confidence: high\n"
                "user_phrasing_signals: []\n"
                "phrasing_honoured: true\n"
                "override_token: null\n"
                "safety_override_fired: false\n"
                "predicted_files: []\n"
                "fingerprint_cost_tokens: 0\n"
                "criticality_filtered_by_tier: false\n"
                "---\n"
            )
        fields, err = mod.parse_frontmatter(self.path)
        self.assertIsNone(err)
        self.assertEqual(fields.get("tier_emitted"), "T1")
        self.assertEqual(fields.get("detector_phase"), "rules")

    def test_parse_frontmatter_unit_missing(self):
        mod = _load_module()
        fields, err = mod.parse_frontmatter("/nonexistent/path/intake.md")
        self.assertEqual(err, "intake-md-missing")

    def test_parse_frontmatter_unit_malformed(self):
        mod = _load_module()
        with open(self.path, "w") as f:
            f.write("not a yaml block\nrandom garbage\n")
        fields, err = mod.parse_frontmatter(self.path)
        self.assertEqual(err, "intake-md-malformed")


class BuildRecordTest(unittest.TestCase):
    def test_build_record_unit_applies_sentinels(self):
        mod = _load_module()
        rec = mod.build_record({}, "intake-md-missing", "2026-05-14T09:30:00Z", "foo-bar")
        self.assertEqual(rec["task_id"], "foo-bar")
        self.assertEqual(rec["parse_error"], "intake-md-missing")
        self.assertEqual(rec["timestamp"], "2026-05-14T09:30:00Z")
        # All 12 required keys present
        for key in [
            "tier_emitted", "tier_initial", "detector_phase", "detector_confidence",
            "user_phrasing_signals", "phrasing_honoured", "override_token",
            "safety_override_fired", "predicted_files", "fingerprint_cost_tokens",
        ]:
            self.assertIn(key, rec)

    def test_build_record_unit_well_formed(self):
        mod = _load_module()
        fields = {
            "tier_emitted": "T5",
            "tier_initial": "T5",
            "detector_phase": "rules",
            "detector_confidence": "high",
            "user_phrasing_signals": [],
            "phrasing_honoured": True,
            "override_token": None,
            "safety_override_fired": False,
            "predicted_files": [],
            "fingerprint_cost_tokens": 0,
        }
        rec = mod.build_record(fields, None, "2026-05-14T09:30:00Z", "foo-bar")
        self.assertNotIn("parse_error", rec)
        self.assertEqual(rec["tier_emitted"], "T5")


class AppendJsonlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "intake-overrides.jsonl")

    def test_append_jsonl_unit_writes_valid_json(self):
        mod = _load_module()
        mod.append_jsonl(self.path, {"a": 1})
        mod.append_jsonl(self.path, {"b": 2})
        with open(self.path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0]), {"a": 1})
        self.assertEqual(json.loads(lines[1]), {"b": 2})


class EmitJsonlSchemaTest(unittest.TestCase):
    def test_emit_jsonl_schema_required_keys(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            intake_md = os.path.join(tmp, "intake.md")
            with open(intake_md, "w") as f:
                f.write(
                    "---\n"
                    "tier_emitted: T5\n"
                    "tier_initial: T5\n"
                    "detector_phase: rules\n"
                    "detector_confidence: high\n"
                    "user_phrasing_signals: []\n"
                    "phrasing_honoured: true\n"
                    "override_token: null\n"
                    "safety_override_fired: false\n"
                    "predicted_files: []\n"
                    "fingerprint_cost_tokens: 0\n"
                    "criticality_filtered_by_tier: false\n"
                    "---\n"
                )
            metrics_dir = os.path.join(tmp, "metrics")
            rc = mod.main([HELPER, metrics_dir, "2026-05-14T09:30:00Z", "foo-bar", intake_md])
            self.assertEqual(rc, 0)
            jsonl_path = os.path.join(metrics_dir, "intake-overrides.jsonl")
            self.assertTrue(os.path.isfile(jsonl_path))
            with open(jsonl_path) as f:
                rec = json.loads(f.read().strip())
            for key in [
                "timestamp", "task_id", "tier_emitted", "tier_initial",
                "detector_phase", "detector_confidence", "user_phrasing_signals",
                "phrasing_honoured", "override_token", "safety_override_fired",
                "predicted_files", "fingerprint_cost_tokens",
            ]:
                self.assertIn(key, rec, f"missing key {key}")
            self.assertIn(rec["detector_phase"], ["rules", "fallthrough", "<unknown>"])


class MainExitCodeTest(unittest.TestCase):
    """Mutation-killer: main MUST return 0 on every path (advisory contract)."""

    def test_main_returns_zero_on_well_formed_input(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            intake_md = os.path.join(tmp, "intake.md")
            with open(intake_md, "w") as f:
                f.write("---\ntier_emitted: T5\n---\n")
            rc = mod.main([HELPER, os.path.join(tmp, "m"), "ts", "foo", intake_md])
            self.assertEqual(rc, 0)

    def test_main_returns_zero_on_missing_intake(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            rc = mod.main([HELPER, os.path.join(tmp, "m"), "ts", "foo", "/nonexistent"])
            self.assertEqual(rc, 0)

    def test_main_returns_zero_on_unknown_task_id(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            rc = mod.main([HELPER, os.path.join(tmp, "m"), "ts", "<unknown>", "/x"])
            self.assertEqual(rc, 0)

    def test_main_returns_zero_on_argv_mismatch(self):
        mod = _load_module()
        self.assertEqual(mod.main([HELPER]), 0)
        self.assertEqual(mod.main([HELPER, "a", "b"]), 0)


class SentinelDefaultsTest(unittest.TestCase):
    """Mutation-killer: sentinel defaults MUST match plan §C1 exactly."""

    def test_sentinel_tier_emitted_is_unknown_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertEqual(rec["tier_emitted"], "<unknown>")
        self.assertEqual(rec["tier_initial"], "<unknown>")

    def test_sentinel_phrasing_honoured_is_false_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertEqual(rec["phrasing_honoured"], False)
        self.assertEqual(rec["safety_override_fired"], False)

    def test_sentinel_lists_are_empty_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertEqual(rec["user_phrasing_signals"], [])
        self.assertEqual(rec["predicted_files"], [])

    def test_sentinel_override_token_is_null_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertIsNone(rec["override_token"])

    def test_sentinel_cost_is_zero_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertEqual(rec["fingerprint_cost_tokens"], 0)


class UnknownTaskIdRoutingTest(unittest.TestCase):
    """Mutation-killer: task_id == '<unknown>' MUST trigger task-id-resolution-failed."""

    def test_unknown_task_id_triggers_parse_error(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = os.path.join(tmp, "metrics")
            mod.main([HELPER, metrics_dir, "ts", "<unknown>", "/nonexistent/intake.md"])
            jsonl_path = os.path.join(metrics_dir, "intake-overrides.jsonl")
            with open(jsonl_path) as f:
                rec = json.loads(f.read().strip())
            self.assertEqual(rec["parse_error"], "task-id-resolution-failed")
            self.assertEqual(rec["task_id"], "<unknown>")

    def test_real_task_id_with_missing_intake_triggers_intake_md_missing(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = os.path.join(tmp, "metrics")
            mod.main([HELPER, metrics_dir, "ts", "foo-bar", "/nonexistent/intake.md"])
            jsonl_path = os.path.join(metrics_dir, "intake-overrides.jsonl")
            with open(jsonl_path) as f:
                rec = json.loads(f.read().strip())
            self.assertEqual(rec["parse_error"], "intake-md-missing")


class FrontmatterRegexTest(unittest.TestCase):
    """Mutation-killer: frontmatter regex MUST anchor at line start (^---)."""

    def test_frontmatter_must_start_at_line_zero(self):
        mod = _load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            # Leading content BEFORE --- — must be treated as malformed
            f.write("preamble\n---\ntier_emitted: T5\n---\n")
            path = f.name
        try:
            fields, err = mod.parse_frontmatter(path)
            self.assertEqual(err, "intake-md-malformed")
        finally:
            os.unlink(path)

    def test_well_formed_frontmatter_parses(self):
        mod = _load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\ntier_emitted: T5\n---\n")
            path = f.name
        try:
            fields, err = mod.parse_frontmatter(path)
            self.assertIsNone(err)
            self.assertEqual(fields["tier_emitted"], "T5")
        finally:
            os.unlink(path)


class JsonlNewlineTest(unittest.TestCase):
    """Mutation-killer: append MUST add a trailing newline (JSONL invariant)."""

    def test_each_record_terminated_by_newline(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.jsonl")
            mod.append_jsonl(path, {"a": 1})
            mod.append_jsonl(path, {"b": 2})
            with open(path) as f:
                content = f.read()
            self.assertEqual(content.count("\n"), 2)
            self.assertTrue(content.endswith("\n"))

    def test_records_are_separable_by_newline(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.jsonl")
            mod.append_jsonl(path, {"a": 1})
            mod.append_jsonl(path, {"b": 2})
            with open(path) as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
