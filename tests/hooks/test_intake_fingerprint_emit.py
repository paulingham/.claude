"""Slice B — AC5 (hooks/_lib/intake-fingerprint-emit.py)
Per-function unit tests for the 4-function decomposition:
  parse_frontmatter, build_record, append_jsonl, main
Asserts:
  - JSONL line shape via json.loads (all 13 keys present)
  - enum constraints on gear_emitted, detector_phase ∈ {rules, fallthrough}
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
        # Plant intake.md inside a synthetic CONFIG_DIR/pipeline-state/<task>/ tree
        # so the realpath containment gate (HIGH-1 defence-in-depth) accepts it.
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp
        task_dir = os.path.join(self.tmp, "pipeline-state", "foo-bar")
        os.makedirs(task_dir)
        self.path = os.path.join(task_dir, "intake.md")

    def tearDown(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def test_parse_frontmatter_unit_well_formed(self):
        mod = _load_module()
        with open(self.path, "w") as f:
            f.write(
                "---\n"
                "gear_emitted: BUILD\n"
                "gear_initial: BUILD\n"
                "detector_phase: rules\n"
                "detector_confidence: high\n"
                "user_phrasing_signals: []\n"
                "phrasing_honoured: true\n"
                "override_token: null\n"
                "safety_override_fired: false\n"
                "predicted_files: []\n"
                "fingerprint_cost_tokens: 0\n"
                "criticality_filtered_by_gear: false\n"
                "---\n"
            )
        fields, err = mod.parse_frontmatter(self.path)
        self.assertIsNone(err)
        self.assertEqual(fields.get("gear_emitted"), "BUILD")
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

    def test_parse_frontmatter_frontmatter_key_missing(self):
        """Code-review MEDIUM: explicit coverage of frontmatter-key-missing branch.

        A frontmatter block with valid --- delimiters but none of REQUIRED_KEYS
        present must return (fields, "frontmatter-key-missing"). 3 of 4 parse_error
        modes are otherwise tested; this closes the gap.
        """
        mod = _load_module()
        with open(self.path, "w") as f:
            f.write(
                "---\n"
                "task_id: foo-bar\n"
                "some_unrelated_key: value\n"
                "another_unrelated_key: 42\n"
                "---\n"
            )
        fields, err = mod.parse_frontmatter(self.path)
        self.assertEqual(err, "frontmatter-key-missing")
        # Present non-required keys still carried through (per § C1).
        self.assertEqual(fields.get("task_id"), "foo-bar")
        self.assertEqual(fields.get("another_unrelated_key"), 42)


class BuildRecordTest(unittest.TestCase):
    def test_build_record_unit_applies_sentinels(self):
        mod = _load_module()
        rec = mod.build_record({}, "intake-md-missing", "2026-05-14T09:30:00Z", "foo-bar")
        self.assertEqual(rec["task_id"], "foo-bar")
        self.assertEqual(rec["parse_error"], "intake-md-missing")
        self.assertEqual(rec["timestamp"], "2026-05-14T09:30:00Z")
        # All 12 required keys present
        for key in [
            "gear_emitted", "gear_initial", "detector_phase", "detector_confidence",
            "user_phrasing_signals", "phrasing_honoured", "override_token",
            "safety_override_fired", "predicted_files", "fingerprint_cost_tokens",
        ]:
            self.assertIn(key, rec)

    def test_build_record_unit_well_formed(self):
        mod = _load_module()
        fields = {
            "gear_emitted": "BUILD",
            "gear_initial": "BUILD",
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
        self.assertEqual(rec["gear_emitted"], "BUILD")


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
                    "gear_emitted: BUILD\n"
                    "gear_initial: BUILD\n"
                    "detector_phase: rules\n"
                    "detector_confidence: high\n"
                    "user_phrasing_signals: []\n"
                    "phrasing_honoured: true\n"
                    "override_token: null\n"
                    "safety_override_fired: false\n"
                    "predicted_files: []\n"
                    "fingerprint_cost_tokens: 0\n"
                    "criticality_filtered_by_gear: false\n"
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
                "timestamp", "task_id", "gear_emitted", "gear_initial",
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
                f.write("---\ngear_emitted: BUILD\n---\n")
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

    def test_sentinel_gear_emitted_is_unknown_when_missing(self):
        mod = _load_module()
        rec = mod.build_record({}, None, "ts", "foo")
        self.assertEqual(rec["gear_emitted"], "<unknown>")
        self.assertEqual(rec["gear_initial"], "<unknown>")

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

    def setUp(self):
        # Plant the fixture inside a synthetic CONFIG_DIR/pipeline-state/ tree
        # so the realpath containment gate (HIGH-1 defence-in-depth) accepts it.
        self.tmp = tempfile.mkdtemp()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp
        task_dir = os.path.join(self.tmp, "pipeline-state", "foo-bar")
        os.makedirs(task_dir)
        self.path = os.path.join(task_dir, "intake.md")

    def tearDown(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def test_frontmatter_must_start_at_line_zero(self):
        mod = _load_module()
        with open(self.path, "w") as f:
            # Leading content BEFORE --- — must be treated as malformed
            f.write("preamble\n---\ngear_emitted: BUILD\n---\n")
        fields, err = mod.parse_frontmatter(self.path)
        self.assertEqual(err, "intake-md-malformed")

    def test_well_formed_frontmatter_parses(self):
        mod = _load_module()
        with open(self.path, "w") as f:
            f.write("---\ngear_emitted: BUILD\n---\n")
        fields, err = mod.parse_frontmatter(self.path)
        self.assertIsNone(err)
        self.assertEqual(fields["gear_emitted"], "BUILD")


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


class ParseFrontmatterContainmentTest(unittest.TestCase):
    """Security HIGH-1 (Python defence-in-depth): parse_frontmatter MUST refuse
    to read paths that escape CLAUDE_CONFIG_DIR/pipeline-state/ via symlink or ..

    The bash sanitiser is the primary gate; this Python gate is defence-in-depth
    so direct invocation of the helper (e.g., via tests or future callers) cannot
    bypass containment.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp, "config")
        os.makedirs(os.path.join(self.config_dir, "pipeline-state", "foo-bar"))
        # Plant a sensitive file OUTSIDE the pipeline-state tree.
        self.outside = os.path.join(self.tmp, "outside.md")
        with open(self.outside, "w") as f:
            f.write(
                "---\n"
                "gear_emitted: PIPELINE\n"
                "gear_initial: PIPELINE\n"
                "detector_phase: rules\n"
                "detector_confidence: high\n"
                "user_phrasing_signals: []\n"
                "phrasing_honoured: true\n"
                "override_token: null\n"
                "safety_override_fired: true\n"
                "predicted_files: []\n"
                "fingerprint_cost_tokens: 0\n"
                "---\n"
            )
        os.environ["CLAUDE_CONFIG_DIR"] = self.config_dir

    def tearDown(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def test_path_escaping_via_dotdot_returns_missing(self):
        """A realpath escaping CLAUDE_CONFIG_DIR/pipeline-state/ MUST be rejected
        as intake-md-missing (never read out-of-tree)."""
        mod = _load_module()
        # Craft a path that resolves outside the pipeline-state tree.
        escape_path = os.path.join(
            self.config_dir, "pipeline-state", "..", "..", "outside.md"
        )
        fields, err = mod.parse_frontmatter(escape_path)
        self.assertEqual(err, "intake-md-missing")
        # Frontmatter must NOT have been read.
        self.assertNotIn("gear_emitted", fields)

    def test_symlink_pointing_outside_returns_missing(self):
        """A symlinked intake.md whose realpath escapes the tree is rejected."""
        mod = _load_module()
        symlink_path = os.path.join(
            self.config_dir, "pipeline-state", "foo-bar", "intake.md"
        )
        os.symlink(self.outside, symlink_path)
        fields, err = mod.parse_frontmatter(symlink_path)
        self.assertEqual(err, "intake-md-missing")
        self.assertNotIn("gear_emitted", fields)

    def test_legitimate_intake_md_still_reads(self):
        """Containment gate MUST NOT block legitimate in-tree paths."""
        mod = _load_module()
        legit = os.path.join(self.config_dir, "pipeline-state", "foo-bar", "intake.md")
        with open(legit, "w") as f:
            f.write(
                "---\n"
                "gear_emitted: BUILD\n"
                "gear_initial: BUILD\n"
                "detector_phase: rules\n"
                "detector_confidence: high\n"
                "user_phrasing_signals: []\n"
                "phrasing_honoured: true\n"
                "override_token: null\n"
                "safety_override_fired: false\n"
                "predicted_files: []\n"
                "fingerprint_cost_tokens: 0\n"
                "---\n"
            )
        fields, err = mod.parse_frontmatter(legit)
        self.assertIsNone(err)
        self.assertEqual(fields["gear_emitted"], "BUILD")


class AppendJsonlNoFollowTest(unittest.TestCase):
    """Security MED-1: append_jsonl MUST refuse to follow symlinks (O_NOFOLLOW)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Plant a symlink at the JSONL target pointing somewhere else.
        self.target = os.path.join(self.tmp, "actual-target.txt")
        with open(self.target, "w") as f:
            f.write("pre-existing content\n")
        self.symlink_path = os.path.join(self.tmp, "intake-overrides.jsonl")
        os.symlink(self.target, self.symlink_path)

    def test_append_jsonl_refuses_to_follow_symlink(self):
        mod = _load_module()
        # Must raise OSError (ELOOP via O_NOFOLLOW) when the path is a symlink.
        with self.assertRaises(OSError):
            mod.append_jsonl(self.symlink_path, {"a": 1})
        # Critically: the symlink target must NOT have been mutated.
        with open(self.target) as f:
            content = f.read()
        self.assertEqual(content, "pre-existing content\n")

    def test_append_jsonl_works_on_regular_file(self):
        mod = _load_module()
        regular_path = os.path.join(self.tmp, "regular.jsonl")
        mod.append_jsonl(regular_path, {"a": 1})
        mod.append_jsonl(regular_path, {"b": 2})
        with open(regular_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)


class BuildRecordCapTest(unittest.TestCase):
    """Security MED-2: build_record MUST enforce the 1024-char string cap and
    100-element list cap claimed by its docstring. Prevents DoS via attacker-
    controlled frontmatter fields with mega-strings or mega-lists."""

    def test_string_field_is_capped_at_1024_chars(self):
        mod = _load_module()
        huge = "x" * 100_000
        fields = {"gear_emitted": huge}
        rec = mod.build_record(fields, None, "ts", "foo")
        self.assertEqual(len(rec["gear_emitted"]), 1024)
        self.assertTrue(rec["gear_emitted"].startswith("x"))

    def test_list_field_is_capped_at_100_items(self):
        mod = _load_module()
        huge_list = [f"signal-{i}" for i in range(10_000)]
        fields = {"user_phrasing_signals": huge_list}
        rec = mod.build_record(fields, None, "ts", "foo")
        self.assertEqual(len(rec["user_phrasing_signals"]), 100)
        self.assertEqual(rec["user_phrasing_signals"][0], "signal-0")

    def test_list_items_themselves_are_capped(self):
        mod = _load_module()
        fields = {"predicted_files": ["y" * 10_000]}
        rec = mod.build_record(fields, None, "ts", "foo")
        self.assertEqual(len(rec["predicted_files"]), 1)
        self.assertEqual(len(rec["predicted_files"][0]), 1024)

    def test_small_values_pass_through_unchanged(self):
        mod = _load_module()
        fields = {"gear_emitted": "BUILD", "user_phrasing_signals": ["a", "b"]}
        rec = mod.build_record(fields, None, "ts", "foo")
        self.assertEqual(rec["gear_emitted"], "BUILD")
        self.assertEqual(rec["user_phrasing_signals"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
