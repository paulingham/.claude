"""
Spec-blind black-box behavioural tests for the swe-pruner hook.

These tests are authored from the AC plan and the hook's OBSERVABLE CONTRACT
ONLY — no swe_pruner.py source is read. The hook is invoked as a subprocess;
JSONL output is read from the filesystem. Tests import nothing from hooks/_lib.

Each test is keyed to one or more ACs from:
  pipeline-state/swe-pruner-advisory-context-filter/plan.md

The goal: catch the SWE-Bench-Pro-vs-Verified failure mode where build-time
tests codify the same misconception as the production code. These tests are
entirely independent of how the scorer is implemented.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Infrastructure — invoke the hook as a black box
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _REPO_ROOT / "hooks" / "pre-agent-swe-pruner.sh"

# Find site-packages from the current interpreter so the hook subprocess can
# locate swe_pruner.py via PYTHONPATH.
_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _build_env(tmpdir, session="spec-blind-test", extra_env=None):
    """Build the subprocess environment for a hook invocation."""
    proc_env = {}
    proc_env["PATH"] = os.environ.get("PATH", "")
    proc_env["HOME"] = tmpdir
    proc_env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    proc_env["CLAUDE_PLUGIN_DATA"] = tmpdir
    proc_env["CLAUDE_SESSION_ID"] = session
    proc_env["PYTHONPATH"] = ":".join(filter(None, [
        str(_REPO_ROOT / "hooks" / "_lib"),
        _SITE_PP,
        os.environ.get("PYTHONPATH", ""),
    ]))
    proc_env["CLAUDE_HOOK_PROFILE"] = "standard"
    if extra_env:
        proc_env.update(extra_env)
    return proc_env


def _invoke_hook(payload_or_str, tmpdir, *, session="spec-blind-test", extra_env=None):
    """
    Run the hook subprocess and return (CompletedProcess, first_record_or_None).

    IMPORTANT: must be called while tmpdir still exists (i.e. inside the
    'with tempfile.TemporaryDirectory()' block). We read the JSONL record
    immediately here so callers do not need to worry about tmpdir lifetime.
    """
    proc_env = _build_env(tmpdir, session=session, extra_env=extra_env)
    input_str = (
        json.dumps(payload_or_str)
        if isinstance(payload_or_str, dict)
        else str(payload_or_str)
    )
    result = subprocess.run(
        ["bash", str(_HOOK)],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=20,
        env=proc_env,
    )
    # Read the JSONL record NOW while tmpdir is alive
    jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
    first_record = None
    jsonl_written = bool(jsonl_files)
    if jsonl_files:
        text = jsonl_files[0].read_text().strip()
        if text:
            first_record = json.loads(text.splitlines()[0])
    return result, jsonl_written, first_record


def _make_payload(subagent_type, prompt):
    """Construct a minimal valid Agent PreToolUse payload."""
    return {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": subagent_type,
            "prompt": prompt,
            "model": "claude-sonnet-4-6",
        },
    }


# ---------------------------------------------------------------------------
# AC7 / AC8 / AC9 — Advisory invariant: stdout ALWAYS empty, exit code ALWAYS 0
# (Black-box complement to the unit tests; deliberately orthogonal payloads.)
# ---------------------------------------------------------------------------

class TestAdvisoryInvariantStdoutEmpty(unittest.TestCase):
    """
    INVARIANT 1 (AC9): the hook NEVER writes to stdout regardless of payload.

    These are black-box variants with payloads NOT present in the build-time
    test suite — specifically: large prompt, fully-relevant prompt, unicode,
    and a payload that has no 'tool_input' key at all.
    """

    def test_stdout_empty_large_irrelevant_prompt(self):
        # AC9: large blob of meteorological text — completely irrelevant to any agent goal
        big_irrelevant = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            + (
                "The cumulonimbus cloud formation reached 45,000 feet.\n"
                "Orographic precipitation occurs when moist air is forced upward.\n"
                "El Nino events redistribute ocean heat causing drought patterns.\n"
            ) * 80
        )
        payload = _make_payload("software-engineer", big_irrelevant)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(payload, tmpdir)
        self.assertEqual(
            result.stdout, "",
            f"Hook wrote to stdout (INVARIANT VIOLATION). stdout={result.stdout!r}"
        )

    def test_stdout_empty_fully_relevant_prompt(self):
        # AC9: prompt whose every line is dense with goal keywords
        relevant = (
            "## Role\n"
            "software-engineer: build the authentication service.\n"
            "authentication authentication auth service engineer build.\n"
        ) * 20
        payload = _make_payload("software-engineer", relevant)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(payload, tmpdir)
        self.assertEqual(
            result.stdout, "",
            f"Hook wrote to stdout on fully-relevant prompt: {result.stdout!r}"
        )

    def test_stdout_empty_unicode_payload(self):
        # AC9: unicode characters in prompt — must not cause hook to write anything
        unicode_prompt = "## Scratchpad\n中文内容测试\n\xe9\xe0\xfc\xf6\n"
        payload = _make_payload("software-engineer", unicode_prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(payload, tmpdir)
        self.assertEqual(result.stdout, "")

    def test_stdout_empty_no_tool_input_key(self):
        # AC8: malformed payload — missing tool_input entirely
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook({"tool_name": "Agent", "other": "stuff"}, tmpdir)
        self.assertEqual(result.stdout, "")

    def test_exit_zero_all_malformed_variants(self):
        # AC7 / AC8: exit code must be 0 for every degenerate input
        degenerate_inputs = [
            "",                                         # empty stdin
            "not json at all",                          # not JSON
            "{}",                                       # empty JSON object
            '{"tool_name":"NotAgent"}',                 # wrong tool name
            '{"tool_name":"Agent","tool_input":{}}',    # tool_input present but empty
        ]
        for raw in degenerate_inputs:
            with self.subTest(payload=raw[:40]):
                with tempfile.TemporaryDirectory() as tmpdir:
                    result, _, _ = _invoke_hook(raw, tmpdir)
                raw_preview = repr(raw)[:40]
                self.assertEqual(
                    result.returncode, 0,
                    f"Hook exited {result.returncode} for input {raw_preview}: "
                    f"stderr={result.stderr!r}"
                )
                self.assertEqual(
                    result.stdout, "",
                    f"Hook wrote stdout for degenerate input {raw_preview}"
                )

    def test_exit_zero_disabled(self):
        # AC7: CLAUDE_DISABLE_SWE_PRUNER=1 — still exits 0
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nbuild the service\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(
                payload, tmpdir,
                extra_env={"CLAUDE_DISABLE_SWE_PRUNER": "1"}
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_no_modified_tool_input_key_in_stdout(self):
        # AC9: the literal string 'modified_tool_input' must never appear in stdout
        # (that key signals context mutation — strictly forbidden in advisory mode)
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nbuild the authentication system\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(payload, tmpdir)
        self.assertNotIn("modified_tool_input", result.stdout)


# ---------------------------------------------------------------------------
# AC17 / AC5 — Relevance keying: irrelevant block → drops; relevant → few/none
# ---------------------------------------------------------------------------

class TestRelevanceKeying(unittest.TestCase):
    """
    AC17: An irrelevant block must yield proposed drops; a relevant block must not.

    We test this purely by invoking the hook and reading the JSONL output.
    No implementation source is accessed.
    """

    def test_irrelevant_block_yields_proposed_drops(self):
        """
        AC17: A prompt whose injected scratchpad block is about meteorology
        (completely unrelated to 'software-engineer' building an auth service)
        should produce at least one proposed_drop range in the JSONL.
        """
        irrelevant_block = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "Cumulus clouds form when warm moist air rises rapidly.\n"
            "Barometric pressure drops before a storm front arrives.\n"
            "The jet stream influences surface weather patterns.\n"
            "Precipitation measurements use a rain gauge device.\n"
            "Hurricane categories are based on wind speed.\n"
            "Thermohaline circulation drives deep ocean currents.\n"
            "Troposphere extends from surface to about 12 kilometres.\n"
            "Polar vortex disruption causes cold air outbreaks.\n"
        ) * 3
        role_section = "## Role\nsoftware-engineer: build the authentication service.\n"
        prompt = irrelevant_block + role_section

        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "JSONL was not written for valid payload")
        self.assertIsNotNone(record, "JSONL was empty")

        any_drops = any(
            len(b.get("proposed_drop_ranges", [])) > 0
            for b in record.get("blocks_analyzed", [])
        )
        self.assertTrue(
            any_drops,
            "Expected proposed drops for an irrelevant meteorology block, "
            f"but got none. blocks_analyzed={record.get('blocks_analyzed')}"
        )

    def test_relevant_block_yields_fewer_drops_than_irrelevant(self):
        """
        AC17: A prompt that is highly relevant to the agent goal should yield
        fewer proposed drop lines than an irrelevant prompt.
        """
        irrelevant_prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            + (
                "Orographic lift causes precipitation on windward slopes.\n"
                "Sea surface temperature anomalies affect hurricane intensity.\n"
                "The tropopause marks the boundary of the troposphere.\n"
            ) * 10
            + "## Role\nsoftware-engineer: build the authentication service.\n"
        )
        relevant_prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            + (
                "The authentication service must be built using TDD.\n"
                "Software engineer: implement the auth service endpoints.\n"
                "Build the authentication module with proper test coverage.\n"
            ) * 10
            + "## Role\nsoftware-engineer: build the authentication service.\n"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, irr_record = _invoke_hook(
                _make_payload("software-engineer", irrelevant_prompt),
                tmpdir,
                session="spec-blind-irrelevant"
            )
        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, rel_record = _invoke_hook(
                _make_payload("software-engineer", relevant_prompt),
                tmpdir,
                session="spec-blind-relevant"
            )

        self.assertIsNotNone(irr_record, "Hook failed on irrelevant prompt")
        self.assertIsNotNone(rel_record, "Hook failed on relevant prompt")

        irrelevant_drops = irr_record.get("total_proposed_drop_lines", 0)
        relevant_drops = rel_record.get("total_proposed_drop_lines", 0)

        self.assertGreater(
            irrelevant_drops, relevant_drops,
            f"Expected irrelevant prompt ({irrelevant_drops} drops) to have "
            f"more drops than relevant prompt ({relevant_drops} drops). "
            "The scorer appears not to be keyed to the agent goal."
        )


# ---------------------------------------------------------------------------
# AC3 / AC5 — Syntax preservation: fenced code blocks never fully dropped
# ---------------------------------------------------------------------------

class TestSyntaxPreservation(unittest.TestCase):
    """
    AC3 / AC5 (INVARIANT 2): syntax scaffolding — specifically fenced code
    blocks — must NEVER be proposed for complete removal.
    """

    def test_fenced_code_block_lines_not_fully_dropped(self):
        """
        AC3 / AC5: the proposed_drop_ranges must not completely cover the
        opening and closing fence lines of an embedded code block.
        """
        fence_content = [
            "## Pipeline Scratchpad (findings from prior agents)",       # line 0
            "Weather patterns unrelated to engineering work.",            # line 1
            "The atmosphere has many layers including the stratosphere.", # line 2
            "```python",                                                   # line 3 — fence open
            "def irrelevant_function():",                                 # line 4
            "    return 'this code is unrelated to weather'",             # line 5
            "```",                                                         # line 6 — fence close
            "More weather text about precipitation and humidity.",        # line 7
            "Clouds form when water vapour cools and condenses.",         # line 8
        ]
        role_section = [
            "## Role",
            "software-engineer: build the authentication service.",
        ]
        prompt = "\n".join(fence_content + role_section) + "\n"

        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "No JSONL written")
        self.assertIsNotNone(record, "JSONL was empty")

        all_ranges = []
        for block in record.get("blocks_analyzed", []):
            for rng in block.get("proposed_drop_ranges", []):
                all_ranges.append(rng)

        # fence lines are at index 3 (open) and 6 (close) within the block
        def covers_line(rng, line_idx):
            start, end = rng
            return start <= line_idx < end

        for rng in all_ranges:
            covers_open = covers_line(rng, 3)
            covers_close = covers_line(rng, 6)
            self.assertFalse(
                covers_open and covers_close,
                f"Drop range {rng} fully covers both fence-open (line 3) and "
                f"fence-close (line 6). INVARIANT 2 violated: "
                f"syntax scaffolding (fenced code block) was proposed for drop."
            )

    def test_fence_open_line_not_proposed_for_drop(self):
        """
        AC3: The fence-open line (```) must never be in a drop range.
        """
        fence_lines = [
            "## Pipeline Scratchpad (findings from prior agents)",
            "Atmospheric pressure varies with altitude in a predictable pattern.",
            "Wind shear affects the intensity of tropical cyclone development.",
            "```bash",                                    # line 3 — fence open
            "echo 'completely irrelevant shell command'", # line 4
            "ls -la /etc/weather-data",                  # line 5
            "```",                                        # line 6 — fence close
            "Further meteorological analysis of precipitation events.",
        ]
        prompt = "\n".join(fence_lines) + "\n## Role\nsoftware-engineer: build auth.\n"

        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        all_ranges = []
        for block in record.get("blocks_analyzed", []):
            for rng in block.get("proposed_drop_ranges", []):
                all_ranges.append(rng)

        # Within the scratchpad block (header line excluded by segment_content_blocks),
        # fence-open (```bash) is at block-line index 2 and fence-close (```) at index 5.
        fence_open_idx = 2
        fence_close_idx = 5

        for rng in all_ranges:
            start, end = rng
            self.assertFalse(
                start <= fence_open_idx < end,
                f"Drop range {rng} covers the fence-open line at block index "
                f"{fence_open_idx}. AC3/INVARIANT 2 violated."
            )
            self.assertFalse(
                start <= fence_close_idx < end,
                f"Drop range {rng} covers the fence-close line at block index "
                f"{fence_close_idx}. AC3/INVARIANT 2 violated."
            )


# ---------------------------------------------------------------------------
# AC13 / AC20 — Token delta: estimated_tokens_saved >= 0 and non-zero for large blobs
# ---------------------------------------------------------------------------

class TestTokenDelta(unittest.TestCase):
    """
    AC13 / AC20: estimated_tokens_saved is present and >= 0 for every block.
    For a large irrelevant blob it must be > 0.
    """

    def test_estimated_tokens_saved_present_and_non_negative(self):
        """AC13: estimated_tokens_saved must be present and >= 0 in every block."""
        prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "Some content about the pipeline.\n"
            "## Role\nsoftware-engineer: build auth service.\n"
        )
        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        self.assertIn("total_estimated_tokens_saved", record,
                      "Missing total_estimated_tokens_saved in JSONL record")
        self.assertGreaterEqual(
            record["total_estimated_tokens_saved"], 0,
            "total_estimated_tokens_saved must be >= 0"
        )
        for block in record.get("blocks_analyzed", []):
            self.assertIn("estimated_tokens_saved", block,
                          f"Block missing estimated_tokens_saved: {block}")
            self.assertGreaterEqual(
                block["estimated_tokens_saved"], 0,
                f"estimated_tokens_saved < 0 in block: {block}"
            )

    def test_token_delta_nonzero_for_large_irrelevant_blob(self):
        """
        AC20: For a large irrelevant blob, total_estimated_tokens_saved must be > 0.

        This catches the 'lying advisory log' pre-mortem failure: if the scorer
        always returns 0, it is useless for the rollout gate decision.
        """
        large_irrelevant = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            + (
                "Cumulonimbus clouds are associated with severe weather phenomena.\n"
                "Orographic precipitation occurs on the windward side of mountains.\n"
                "The Coriolis effect deflects winds to the right in the northern hemisphere.\n"
                "Sea breeze circulation develops due to differential heating of land and sea.\n"
                "Frontal systems separate air masses of different temperature and humidity.\n"
            ) * 80
        )
        prompt = large_irrelevant + "\n## Role\nsoftware-engineer: build auth service.\n"
        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "No JSONL for large irrelevant prompt")
        self.assertIsNotNone(record)

        total_saved = record.get("total_estimated_tokens_saved", 0)
        self.assertGreater(
            total_saved, 0,
            "total_estimated_tokens_saved is 0 for a 400-line irrelevant blob. "
            "This suggests the scorer is always returning 'relevant' (lying advisory log)."
        )


# ---------------------------------------------------------------------------
# AC2 — Canonical header classification: scratchpad header → block_type='scratchpad'
# ---------------------------------------------------------------------------

class TestCanonicalHeaderClassification(unittest.TestCase):
    """
    AC2: '## Pipeline Scratchpad (findings from prior agents)' must be
    classified as block_type='scratchpad' in the JSONL output.
    """

    def test_canonical_scratchpad_header_classified_as_scratchpad(self):
        """AC2: feed the exact canonical header; assert block_type == 'scratchpad'."""
        prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "Findings from the architect: use PostgreSQL for the database.\n"
            "The code-reviewer approved the authentication module.\n"
        )
        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "No JSONL written")
        self.assertIsNotNone(record, "JSONL was empty")

        block_types = [b.get("block_type") for b in record.get("blocks_analyzed", [])]
        self.assertIn(
            "scratchpad", block_types,
            f"Expected block_type='scratchpad' for '## Pipeline Scratchpad ...' header, "
            f"got block_types={block_types!r}"
        )

    def test_scratchpad_block_type_is_valid_enum_value(self):
        """
        AC2 / AC13: every block_type must be one of the valid enum values.
        Valid values per schema: scratchpad, protocol, session_memory, role_doc,
        instincts, unknown.
        """
        VALID_BLOCK_TYPES = {
            "scratchpad", "protocol", "session_memory",
            "role_doc", "instincts", "unknown"
        }
        prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "The security-engineer flagged a CSRF vulnerability.\n"
        )
        payload = _make_payload("software-engineer", prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        for block in record.get("blocks_analyzed", []):
            self.assertIn(
                block.get("block_type"), VALID_BLOCK_TYPES,
                f"block_type {block.get('block_type')!r} not in valid enum: "
                f"{VALID_BLOCK_TYPES}"
            )


# ---------------------------------------------------------------------------
# AC22 — Disable: CLAUDE_DISABLE_SWE_PRUNER=1 writes no JSONL
# ---------------------------------------------------------------------------

class TestDisableEnvvar(unittest.TestCase):
    """
    AC22: When CLAUDE_DISABLE_SWE_PRUNER=1 is set, no JSONL file is written.
    Exit code must still be 0.
    """

    def test_disable_envvar_no_jsonl_written(self):
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nBuild the authentication service.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, _ = _invoke_hook(
                payload, tmpdir,
                extra_env={"CLAUDE_DISABLE_SWE_PRUNER": "1"}
            )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(
            jsonl_written,
            "JSONL should not be written when CLAUDE_DISABLE_SWE_PRUNER=1"
        )

    def test_disable_envvar_zero_stdout(self):
        """AC22 + AC9: disabled hook must write nothing to stdout either."""
        payload = _make_payload(
            "qa-engineer",
            "## Scratchpad\nTest the build pipeline.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, _ = _invoke_hook(
                payload, tmpdir,
                extra_env={"CLAUDE_DISABLE_SWE_PRUNER": "1"}
            )
        self.assertEqual(result.stdout, "")

    def test_disable_envvar_large_payload_still_no_jsonl(self):
        """
        AC22: disable works even with a large valid payload.
        """
        large_prompt = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            + "Orographic lift content.\n" * 50
            + "## Role\nsoftware-engineer: build auth.\n"
        )
        payload = _make_payload("software-engineer", large_prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, _ = _invoke_hook(
                payload, tmpdir,
                extra_env={"CLAUDE_DISABLE_SWE_PRUNER": "1"}
            )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(jsonl_written,
                         "JSONL must not be written when hook is disabled")


# ---------------------------------------------------------------------------
# AC12 — Path traversal guard: ../.. in CLAUDE_SESSION_ID does not escape metrics dir
# ---------------------------------------------------------------------------

class TestPathTraversalGuard(unittest.TestCase):
    """
    AC12: CLAUDE_SESSION_ID containing path traversal characters (../../etc)
    must be sanitised before path construction. The JSONL file must remain
    inside the configured metrics directory — it must NOT be written outside
    CLAUDE_PLUGIN_DATA.
    """

    def test_path_traversal_session_id_stays_inside_metrics_dir(self):
        """
        Feed a session ID with path traversal and verify the JSONL is inside
        CLAUDE_PLUGIN_DATA.
        """
        traversal_session = "../../etc/passwd"
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nBuild the authentication service.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(
                payload, tmpdir,
                session=traversal_session
            )
            self.assertEqual(result.returncode, 0,
                             f"Hook crashed on traversal session ID: {result.stderr}")

            if jsonl_written:
                # Check all found JSONL files are under tmpdir
                jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
                resolved_tmpdir = Path(tmpdir).resolve()
                for jf in jsonl_files:
                    resolved_jf = jf.resolve()
                    self.assertTrue(
                        str(resolved_jf).startswith(str(resolved_tmpdir)),
                        f"JSONL escaped CLAUDE_PLUGIN_DATA! "
                        f"Expected under {resolved_tmpdir}, got {resolved_jf}. "
                        "Path traversal guard failed."
                    )

    def test_path_traversal_session_id_sanitized_in_record(self):
        """
        AC12: The 'session' field in the JSONL record must not contain raw
        path traversal characters (/ or ..).
        """
        traversal_session = "../../etc/shadow"
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nBuild the authentication service.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(
                payload, tmpdir,
                session=traversal_session
            )

        self.assertEqual(result.returncode, 0)
        if not jsonl_written or record is None:
            self.skipTest("Hook did not write JSONL (hook profiled out or disabled)")

        session_val = record.get("session", "")
        self.assertNotIn("..", session_val,
                         f"session field contains '..' (path traversal): {session_val!r}")
        self.assertNotIn("/", session_val,
                         f"session field contains '/' (path traversal): {session_val!r}")

    def test_adjacent_slashes_in_session_id_sanitized(self):
        """
        AC12: A session ID with embedded slashes must be sanitised so the
        path does not traverse outside CLAUDE_PLUGIN_DATA.
        """
        slash_session = "session/with/slashes"
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nBuild the service.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, _ = _invoke_hook(
                payload, tmpdir,
                session=slash_session
            )
            self.assertEqual(result.returncode, 0)

            if jsonl_written:
                jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
                resolved_tmpdir = Path(tmpdir).resolve()
                for jf in jsonl_files:
                    resolved_jf = jf.resolve()
                    self.assertTrue(
                        str(resolved_jf).startswith(str(resolved_tmpdir)),
                        f"JSONL escaped metrics dir with slashed session ID: "
                        f"{resolved_jf} not under {resolved_tmpdir}"
                    )


# ---------------------------------------------------------------------------
# AC21 — E2E: valid payload, JSONL record fields complete
# (Orthogonal check with DIFFERENT agent roles than the build-time integration tests)
# ---------------------------------------------------------------------------

class TestE2EJsonlRecordCompleteness(unittest.TestCase):
    """
    AC21: Valid payload must produce a JSONL record with all required fields.

    These tests use DIFFERENT agent roles and prompt content than the build-time
    integration tests (qa-engineer / architect) to provide orthogonal coverage.
    """

    _REQUIRED_FIELDS = [
        "timestamp", "session", "agent_role", "goal_hash",
        "keyword_count", "blocks_analyzed", "total_lines_analyzed",
        "total_proposed_drop_lines", "total_estimated_tokens_saved",
        "prompt_total_chars", "prompt_estimated_tokens",
    ]

    def test_all_required_fields_present_qa_engineer(self):
        payload = _make_payload(
            "qa-engineer",
            "## Scratchpad\nWrite tests for the login endpoint.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(
                payload, tmpdir, session="e2e-qa"
            )
        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "No JSONL written")
        self.assertIsNotNone(record, "JSONL was empty")
        for field in self._REQUIRED_FIELDS:
            self.assertIn(field, record, f"Missing required field: {field!r}")

    def test_all_required_fields_present_architect(self):
        payload = _make_payload(
            "architect",
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "Design the microservices architecture for the platform.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(
                payload, tmpdir, session="e2e-architect"
            )
        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        self.assertTrue(jsonl_written, "No JSONL written")
        self.assertIsNotNone(record, "JSONL was empty")
        for field in self._REQUIRED_FIELDS:
            self.assertIn(field, record, f"Missing required field: {field!r}")

    def test_agent_role_matches_subagent_type(self):
        """AC21: agent_role in record must match the subagent_type in the payload."""
        for role in ["qa-engineer", "architect", "code-reviewer"]:
            with self.subTest(role=role):
                payload = _make_payload(
                    role,
                    f"## Scratchpad\nPerform the {role} task.\n"
                )
                with tempfile.TemporaryDirectory() as tmpdir:
                    result, _, record = _invoke_hook(
                        payload, tmpdir, session=f"e2e-role-{role}"
                    )
                if record is None:
                    self.skipTest(f"No JSONL for role {role}")
                self.assertEqual(
                    record.get("agent_role"), role,
                    f"agent_role mismatch: expected {role!r}, "
                    f"got {record.get('agent_role')!r}"
                )

    def test_blocks_analyzed_is_list_of_dicts_with_required_subfields(self):
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nBuild the feature.\n## Protocol\nFollow TDD.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        blocks = record.get("blocks_analyzed", None)
        self.assertIsInstance(blocks, list, "blocks_analyzed must be a list")
        for block in blocks:
            self.assertIsInstance(block, dict,
                                  f"Each block must be a dict, got {type(block)}")
            for sub_field in ["block_type", "total_lines", "proposed_drop_lines",
                               "proposed_drop_ranges", "estimated_tokens_saved"]:
                self.assertIn(sub_field, block,
                              f"Block missing sub-field {sub_field!r}: {block}")

    def test_numeric_fields_are_non_negative(self):
        payload = _make_payload(
            "software-engineer",
            "## Scratchpad\nRefactor the authentication module.\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        for field in ["total_lines_analyzed", "total_proposed_drop_lines",
                      "total_estimated_tokens_saved", "prompt_total_chars",
                      "prompt_estimated_tokens", "keyword_count"]:
            value = record.get(field)
            self.assertIsNotNone(value, f"Field {field!r} is missing from record")
            self.assertIsInstance(value, (int, float),
                                  f"Field {field!r} must be numeric, got {type(value)}")
            self.assertGreaterEqual(value, 0,
                                    f"Field {field!r} must be >= 0, got {value}")

    def test_prompt_total_chars_matches_actual_prompt_length(self):
        """
        AC13 / AC21: prompt_total_chars should equal len(prompt).
        """
        prompt_text = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "The build succeeded on the main branch.\n"
            "## Role\nsoftware-engineer: refactor the auth service.\n"
        )
        payload = _make_payload("software-engineer", prompt_text)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)
        self.assertEqual(
            record.get("prompt_total_chars"), len(prompt_text),
            f"prompt_total_chars {record.get('prompt_total_chars')} != "
            f"actual prompt length {len(prompt_text)}"
        )

    def test_prompt_estimated_tokens_is_chars_div_4(self):
        """
        AC13: prompt_estimated_tokens = prompt_total_chars // 4 (per schema).
        """
        prompt_text = (
            "## Pipeline Scratchpad (findings from prior agents)\n"
            "The build is ready for deployment.\n"
            "## Role\nsoftware-engineer: deploy the service.\n"
        )
        payload = _make_payload("software-engineer", prompt_text)
        with tempfile.TemporaryDirectory() as tmpdir:
            result, jsonl_written, record = _invoke_hook(payload, tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(jsonl_written)
        self.assertIsNotNone(record)

        chars = record.get("prompt_total_chars", 0)
        expected_tokens = chars // 4
        self.assertEqual(
            record.get("prompt_estimated_tokens"), expected_tokens,
            f"prompt_estimated_tokens={record.get('prompt_estimated_tokens')} "
            f"!= chars//4={expected_tokens} (chars={chars})"
        )


if __name__ == "__main__":
    unittest.main()
