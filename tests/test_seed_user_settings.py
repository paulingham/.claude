"""Tests for hooks/_lib/seed_user_settings.py.

All tests that touch the write path bind CLAUDE_SETTINGS_PATH to a tempfile
so they never mutate the real ~/.claude/settings.json.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Break-glass keys that must never appear in any seed write.
BREAK_GLASS_KEYS = {
    "CLAUDE_DISABLE_QUALITY_GATE",
    "CLAUDE_DISABLE_TOOL_ALLOWLIST",
    "CLAUDE_INTAKE_BACKSTOP",
    "CLAUDE_DISABLE_FRESHNESS_GUARD",
    "CLAUDE_DISABLE_RUNTIME_STATE_GUARD",
}

# The 10 allowlisted toggle keys (order-preserving source of truth for tests).
TOGGLE_KEYS = [
    "CLAUDE_PIPELINE_MODE",
    "CLAUDE_ENABLE_TRACE",
    "CLAUDE_DISABLE_SANDBOX_VERIFY",
    "CLAUDE_DISABLE_VLM_CRITIC",
    "CLAUDE_DISABLE_SWE_PRUNER",
    "CLAUDE_DISABLE_INSTINCT_INJECTION",
    "CLAUDE_DISABLE_WORKTREE_REAPER",
    "CLAUDE_VISIBLE_TEAMS",
    "CLAUDE_PLAN_CACHE_MODE",
    "ENABLE_TOOL_SEARCH",
]


def _import_seed(env_overrides: dict | None = None):
    """Import the module with controlled env; unregister after to stay isolated."""
    saved = {}
    for k, v in (env_overrides or {}).items():
        saved[k] = os.environ.get(k)
        os.environ[k] = v

    # Remove cached version so each test gets a fresh import.
    sys.modules.pop("seed_user_settings", None)
    path = str(REPO_ROOT / "hooks" / "_lib")
    added = path not in sys.path
    if added:
        sys.path.insert(0, path)
    try:
        import seed_user_settings as mod
        return mod
    finally:
        if added:
            sys.path.remove(path)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _make_empty_settings_file() -> Path:
    """Return a temp path pointing at a valid but empty-env settings.json."""
    fd, name = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write('{"env": {}}')
    return Path(name)


def _make_absent_path() -> Path:
    """Return a path that does not exist yet (mkstemp + unlink)."""
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(name).unlink()
    return Path(name)


def _run_seed(settings_path: Path, plugin_root: str | None = None) -> None:
    """Run seed_main with CLAUDE_SETTINGS_PATH pointing at settings_path.

    Always sets CLAUDE_PLUGIN_ROOT to the repo root so the SSOT read finds
    the repo settings.json with _doc_ strings, not the user-installed copy.
    """
    effective_root = plugin_root if plugin_root is not None else str(REPO_ROOT)
    env_overrides: dict = {
        "CLAUDE_SETTINGS_PATH": str(settings_path),
        "CLAUDE_PLUGIN_ROOT": effective_root,
    }
    # Remove any stale cached module.
    sys.modules.pop("seed_user_settings", None)
    saved_env = {}
    for k, v in env_overrides.items():
        saved_env[k] = os.environ.get(k)
        os.environ[k] = v
    path = str(REPO_ROOT / "hooks" / "_lib")
    added = path not in sys.path
    if added:
        sys.path.insert(0, path)
    try:
        import seed_user_settings as mod
        mod.seed_main()
    finally:
        if added:
            sys.path.remove(path)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.modules.pop("seed_user_settings", None)


class TestCreateFileWhenAbsent(unittest.TestCase):
    """AC1: target absent → write 9 toggles + _doc_ siblings."""

    def setUp(self):
        self.path = _make_absent_path()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_creates_file_with_nine_toggles_and_docs_when_absent(self):
        _run_seed(self.path)
        self.assertTrue(self.path.exists(), "seed must create the file")
        data = json.loads(self.path.read_text())
        env = data.get("env", {})
        for key in TOGGLE_KEYS:
            self.assertIn(key, env, f"toggle {key!r} missing from created file")
            doc_key = f"_doc_{key}"
            self.assertIn(doc_key, env, f"_doc_ sibling {doc_key!r} missing")


class TestMergeNeverClobber(unittest.TestCase):
    """AC2: existing values and unrelated keys must be preserved."""

    def setUp(self):
        self.path = _make_empty_settings_file()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_dev_set_toggle_value_never_changed(self):
        """Pre-set CLAUDE_ENABLE_TRACE=1; assert still 1 after seed."""
        data = {"env": {"CLAUDE_ENABLE_TRACE": "1"}}
        self.path.write_text(json.dumps(data))
        _run_seed(self.path)
        result = json.loads(self.path.read_text())
        self.assertEqual(result["env"]["CLAUDE_ENABLE_TRACE"], "1")

    def test_unrelated_dev_keys_preserved_in_order(self):
        """Unrelated keys keep their value and ordering relative to each other."""
        data = {"env": {"MY_CUSTOM_KEY": "keep_me", "ANOTHER_KEY": "also_keep"}}
        self.path.write_text(json.dumps(data))
        _run_seed(self.path)
        result = json.loads(self.path.read_text())
        env_keys = list(result["env"].keys())
        self.assertIn("MY_CUSTOM_KEY", env_keys)
        self.assertIn("ANOTHER_KEY", env_keys)
        self.assertEqual(result["env"]["MY_CUSTOM_KEY"], "keep_me")
        self.assertEqual(result["env"]["ANOTHER_KEY"], "also_keep")
        # Relative order of unrelated keys must be preserved.
        self.assertLess(env_keys.index("MY_CUSTOM_KEY"), env_keys.index("ANOTHER_KEY"))

    def test_only_missing_keys_added(self):
        """If some toggles are present, only absent ones get added."""
        data = {"env": {"CLAUDE_ENABLE_TRACE": "1"}}
        self.path.write_text(json.dumps(data))
        _run_seed(self.path)
        result = json.loads(self.path.read_text())
        # Existing key unchanged.
        self.assertEqual(result["env"]["CLAUDE_ENABLE_TRACE"], "1")
        # Other toggles were added.
        for key in TOGGLE_KEYS:
            self.assertIn(key, result["env"])

    def test_partial_merge_adds_doc_siblings(self):
        """Partial merge must write _doc_ siblings alongside each added toggle.

        test_only_missing_keys_added asserts toggle keys appear but NOT their
        _doc_ siblings. This test independently exercises _insert_doc so that
        a broken doc-path goes RED here even if the key-path stays GREEN.
        """
        data = {"env": {"CLAUDE_ENABLE_TRACE": "1"}}
        self.path.write_text(json.dumps(data))
        _run_seed(self.path)
        result = json.loads(self.path.read_text())
        env = result["env"]
        for key in TOGGLE_KEYS:
            doc_key = f"_doc_{key}"
            self.assertIn(doc_key, env,
                          f"{doc_key!r} missing after partial-merge; "
                          "_insert_doc must add _doc_ siblings in the merge path")

    def test_orphaned_doc_sibling_restored(self):
        """Toggle present but its _doc_ deleted → seed must restore the _doc_.

        _insert_doc skips only when doc_key is already in env. When a user
        deletes a _doc_ sibling while keeping the toggle value, the next
        seed run must restore it without touching the toggle value.
        """
        pivot_key = "CLAUDE_PIPELINE_MODE"
        doc_key = f"_doc_{pivot_key}"
        data = {"env": {pivot_key: "interactive"}}
        self.path.write_text(json.dumps(data))
        _run_seed(self.path)
        result = json.loads(self.path.read_text())
        env = result["env"]
        self.assertEqual(env[pivot_key], "interactive",
                         "pre-existing toggle value must not be overwritten")
        self.assertIn(doc_key, env,
                      f"{doc_key!r} must be restored when toggle exists but _doc_ was absent")


class TestToggleCount(unittest.TestCase):
    """Exact-count guard: TOGGLE_ALLOWLIST must have exactly 10 entries.

    Prevents both accidental addition (11th toggle sneaks in) and
    accidental deletion (one drops silently). The SSOT drift test catches
    set-membership drift; this catches cardinality drift.
    """

    def test_toggle_allowlist_has_exactly_10_entries(self):
        """Implementation TOGGLE_ALLOWLIST must have exactly 10 keys."""
        sys.modules.pop("seed_user_settings", None)
        lib_path = str(REPO_ROOT / "hooks" / "_lib")
        added = lib_path not in sys.path
        if added:
            sys.path.insert(0, lib_path)
        try:
            import seed_user_settings as mod
            self.assertEqual(
                len(mod.TOGGLE_ALLOWLIST), 10,
                f"TOGGLE_ALLOWLIST must have exactly 10 entries; "
                f"got {len(mod.TOGGLE_ALLOWLIST)}: {list(mod.TOGGLE_ALLOWLIST)}",
            )
        finally:
            if added:
                sys.path.remove(lib_path)
            sys.modules.pop("seed_user_settings", None)

    def test_test_toggle_keys_has_exactly_10_entries(self):
        """Test-file TOGGLE_KEYS must stay in sync with the implementation count."""
        self.assertEqual(
            len(TOGGLE_KEYS), 10,
            f"TOGGLE_KEYS in the test file must have exactly 10 entries; "
            f"got {len(TOGGLE_KEYS)}: {TOGGLE_KEYS}",
        )


class TestIdempotent(unittest.TestCase):
    """AC3: second run produces no write when file is already fully seeded."""

    def setUp(self):
        self.path = _make_empty_settings_file()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_second_run_is_byte_and_mtime_identical(self):
        # First run — seeds all keys.
        _run_seed(self.path)
        after_first = self.path.read_bytes()
        mtime_after_first = self.path.stat().st_mtime

        # Sleep briefly so mtime would differ if a write occurred.
        time.sleep(0.05)

        # Second run — must not write.
        _run_seed(self.path)
        self.assertEqual(self.path.read_bytes(), after_first)
        self.assertEqual(self.path.stat().st_mtime, mtime_after_first)


class TestFailClosed(unittest.TestCase):
    """AC4: unparseable JSON → no write, bytes unchanged."""

    def setUp(self):
        fd, name = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{bad json")
        self.path = Path(name)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_unparseable_json_leaves_file_byte_untouched(self):
        before = self.path.read_bytes()
        _run_seed(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_failclosed_line_reverted_goes_red(self):
        """Iron-Law-8: removing the _load_existing except guard causes a crash or write.

        _load_existing catches (json.JSONDecodeError, OSError) and returns None;
        _seed_present then logs a warning and returns without writing.
        WITH the guard: bad JSON → None → early return, bytes unchanged.
        WITHOUT the guard: bad JSON → exception propagates → crash or write,
        read_bytes() would differ or raise.
        """
        before = self.path.read_bytes()
        _run_seed(self.path)
        after = self.path.read_bytes()
        self.assertEqual(before, after,
                         "fail-closed guard must leave unparseable file byte-identical; "
                         "if this fails the except-JSONDecodeError guard was removed")


class TestNoBreakGlassKeys(unittest.TestCase):
    """AC5: no Iron-Law break-glass key can ever appear in a seed write."""

    def setUp(self):
        self.path = _make_absent_path()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_no_iron_law_break_glass_key_ever_seeded(self):
        _run_seed(self.path)
        data = json.loads(self.path.read_text())
        env = data.get("env", {})
        for key in BREAK_GLASS_KEYS:
            self.assertNotIn(key, env, f"break-glass key {key!r} must never be seeded")

    def test_allowlist_excludes_all_break_glass_names(self):
        """Static: ALLOWLIST ∩ BREAK_GLASS == ∅."""
        sys.modules.pop("seed_user_settings", None)
        path = str(REPO_ROOT / "hooks" / "_lib")
        added = path not in sys.path
        if added:
            sys.path.insert(0, path)
        try:
            import seed_user_settings as mod
            overlap = set(mod.TOGGLE_ALLOWLIST) & BREAK_GLASS_KEYS
            self.assertEqual(overlap, set(),
                             f"break-glass keys found in TOGGLE_ALLOWLIST: {overlap}")
        finally:
            if added:
                sys.path.remove(path)
            sys.modules.pop("seed_user_settings", None)


class TestSSOTDriftGuard(unittest.TestCase):
    """AC6: allowlist == repo settings.json dev-toggle set; SSOT reads correctly."""

    def test_allowlist_equals_repo_settings_toggle_set(self):
        """Bidirectional drift guard: allowlist ↔ repo settings.json dev-toggle set.

        Forward: every key in TOGGLE_ALLOWLIST exists in repo settings.json env
        with a value and a _doc_ sibling.
        Reverse: every non-_doc_ key K in repo env where _doc_<K> also exists
        (i.e. every dev toggle) is in TOGGLE_ALLOWLIST — catches a new toggle
        added to settings.json but forgotten in the allowlist.
        Also asserts _FALLBACK_DOCS keys == _FALLBACK_DEFAULTS keys == TOGGLE_ALLOWLIST.
        """
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        env = settings.get("env", {})

        sys.modules.pop("seed_user_settings", None)
        path = str(REPO_ROOT / "hooks" / "_lib")
        added = path not in sys.path
        if added:
            sys.path.insert(0, path)
        try:
            import seed_user_settings as mod
            allowlist_set = set(mod.TOGGLE_ALLOWLIST)

            # Forward: allowlist ⊆ repo env (with _doc_ sibling).
            for key in mod.TOGGLE_ALLOWLIST:
                self.assertIn(key, env,
                              f"allowlist key {key!r} missing from repo settings.json env")
                self.assertIn(f"_doc_{key}", env,
                              f"_doc_{key!r} sibling missing from repo settings.json env")

            # Reverse: repo dev-toggles (keys with _doc_ sibling) ⊆ allowlist.
            repo_dev_toggles = {
                k for k in env
                if not k.startswith("_doc_") and f"_doc_{k}" in env
            }
            for key in repo_dev_toggles:
                self.assertIn(
                    key, allowlist_set,
                    f"repo dev-toggle {key!r} has a _doc_ sibling but is absent from"
                    " TOGGLE_ALLOWLIST — new devs would never receive it",
                )

            # Fallback maps must stay in sync with TOGGLE_ALLOWLIST.
            self.assertEqual(
                set(mod._FALLBACK_DEFAULTS.keys()), allowlist_set,
                "_FALLBACK_DEFAULTS keys must equal TOGGLE_ALLOWLIST",
            )
            self.assertEqual(
                set(mod._FALLBACK_DOCS.keys()), allowlist_set,
                "_FALLBACK_DOCS keys must equal TOGGLE_ALLOWLIST",
            )
        finally:
            if added:
                sys.path.remove(path)
            sys.modules.pop("seed_user_settings", None)

    def test_ssot_read_from_plugin_root_settings(self):
        """AC6: seed reads toggle defaults from CLAUDE_PLUGIN_ROOT/settings.json."""
        with tempfile.TemporaryDirectory() as fixture_root:
            fixture_path = Path(fixture_root)
            # Create a minimal settings.json with a custom toggle default.
            fixture_settings = {
                "env": {
                    "CLAUDE_PIPELINE_MODE": "interactive",
                    "_doc_CLAUDE_PIPELINE_MODE": "doc string",
                    "CLAUDE_ENABLE_TRACE": "1",
                    "_doc_CLAUDE_ENABLE_TRACE": "doc2",
                    "CLAUDE_DISABLE_SANDBOX_VERIFY": "0",
                    "_doc_CLAUDE_DISABLE_SANDBOX_VERIFY": "d3",
                    "CLAUDE_DISABLE_VLM_CRITIC": "0",
                    "_doc_CLAUDE_DISABLE_VLM_CRITIC": "d4",
                    "CLAUDE_DISABLE_SWE_PRUNER": "0",
                    "_doc_CLAUDE_DISABLE_SWE_PRUNER": "d5",
                    "CLAUDE_DISABLE_INSTINCT_INJECTION": "0",
                    "_doc_CLAUDE_DISABLE_INSTINCT_INJECTION": "d6",
                    "CLAUDE_DISABLE_WORKTREE_REAPER": "0",
                    "_doc_CLAUDE_DISABLE_WORKTREE_REAPER": "d7",
                    "CLAUDE_VISIBLE_TEAMS": "0",
                    "_doc_CLAUDE_VISIBLE_TEAMS": "d8",
                    "CLAUDE_PLAN_CACHE_MODE": "off",
                    "_doc_CLAUDE_PLAN_CACHE_MODE": "d9",
                    "ENABLE_TOOL_SEARCH": "true",
                    "_doc_ENABLE_TOOL_SEARCH": "d10",
                }
            }
            (fixture_path / "settings.json").write_text(json.dumps(fixture_settings))
            target_path = fixture_path / "target_settings.json"
            # Run seed pointing at our fixture as CLAUDE_PLUGIN_ROOT.
            _run_seed(target_path, plugin_root=fixture_root)
            result = json.loads(target_path.read_text())
            env = result["env"]
            # Defaults must come from our fixture: interactive and 1, not the hardcoded fallback.
            self.assertEqual(env.get("CLAUDE_PIPELINE_MODE"), "interactive")
            self.assertEqual(env.get("CLAUDE_ENABLE_TRACE"), "1")
            self.assertEqual(env.get("CLAUDE_PLAN_CACHE_MODE"), "off")


class TestFallbackCreateIncludesDocs(unittest.TestCase):
    """Fix 2: fallback path must produce _doc_ siblings, not just toggle values."""

    def setUp(self):
        self.path = _make_absent_path()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_fallback_create_includes_docs(self):
        """When SSOT settings.json is absent, seed must still write all 9 _doc_ siblings."""
        with tempfile.TemporaryDirectory() as empty_root:
            # empty_root has no settings.json — forces the fallback path.
            _run_seed(self.path, plugin_root=empty_root)
            self.assertTrue(self.path.exists(), "seed must create the file via fallback")
            data = json.loads(self.path.read_text())
            env = data.get("env", {})
            for key in TOGGLE_KEYS:
                self.assertIn(key, env, f"toggle {key!r} missing from fallback-created file")
                doc_key = f"_doc_{key}"
                self.assertIn(doc_key, env,
                              f"{doc_key!r} missing from fallback-created file; "
                              "fallback must populate _FALLBACK_DOCS")


class TestNonDictShapeLeavesFileUntouched(unittest.TestCase):
    """Fix 3: valid JSON with wrong shape must not be written or crash."""

    def _write_file(self, content: str) -> Path:
        fd, name = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return Path(name)

    def tearDown(self):
        pass

    def test_list_root_leaves_file_untouched(self):
        """JSON root is a list, not a dict → shape guard returns without writing."""
        path = self._write_file("[1, 2, 3]")
        try:
            before = path.read_bytes()
            _run_seed(path)
            self.assertEqual(path.read_bytes(), before,
                             "list-root file must be byte-identical after seed")
        finally:
            path.unlink(missing_ok=True)

    def test_string_env_leaves_file_untouched(self):
        """env key is a string instead of a dict → shape guard returns without writing."""
        path = self._write_file('{"env": "not-a-dict"}')
        try:
            before = path.read_bytes()
            _run_seed(path)
            self.assertEqual(path.read_bytes(), before,
                             "string-env file must be byte-identical after seed")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
