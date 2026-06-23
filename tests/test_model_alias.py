"""Model alias SSOT tests (Slice 1 — Role→Model Alias Indirection).

Verifies:
- models.json has exactly the three canonical aliases.
- resolve_model_alias maps known aliases to concrete IDs.
- resolve_model_alias passes through unknown (literal) IDs unchanged.
- A one-line ALIASES edit re-points output end-to-end (load-bearing proof).
"""
import importlib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_JSON = REPO_ROOT / "hooks" / "_lib" / "models.json"


def _fresh_model_alias():
    """Reload model_alias module so ALIASES mutation tests get a clean state."""
    import model_alias
    importlib.reload(model_alias)
    return model_alias


class TestModelsJsonHasThreeCanonicalAliases(unittest.TestCase):
    def test_models_json_has_three_canonical_aliases(self):
        import json
        data = json.loads(MODELS_JSON.read_text())
        self.assertEqual(
            data,
            {
                "strong": "claude-opus-4-8",
                "mid": "claude-sonnet-4-6",
                "cheap": "claude-haiku-4-5-20251001",
            },
            "models.json must contain exactly the three canonical aliases",
        )


class TestResolveKnownAliasReturnsConcreteId(unittest.TestCase):
    def test_resolve_known_alias_returns_concrete_id(self):
        from model_alias import resolve_model_alias
        self.assertEqual(resolve_model_alias("strong"), "claude-opus-4-8")
        self.assertEqual(resolve_model_alias("mid"), "claude-sonnet-4-6")
        self.assertEqual(resolve_model_alias("cheap"), "claude-haiku-4-5-20251001")


class TestResolveUnknownAliasPassesThrough(unittest.TestCase):
    def test_resolve_unknown_alias_passes_through(self):
        from model_alias import resolve_model_alias
        self.assertEqual(
            resolve_model_alias("claude-opus-4-7"),
            "claude-opus-4-7",
            "literal model IDs must pass through unchanged (no KeyError, no None)",
        )
        self.assertEqual(
            resolve_model_alias("bogus-model"),
            "bogus-model",
            "unknown alias must be returned as-is",
        )


class TestOneLineEditRepointsStrong(unittest.TestCase):
    def test_one_line_edit_repoints_strong(self):
        """Patching ALIASES["strong"] must flip resolve_model_alias("strong") output.

        This proves the indirection is load-bearing: a single dict edit
        changes what the resolver emits — no other files touched.
        """
        import model_alias
        importlib.reload(model_alias)
        original = model_alias.resolve_model_alias("strong")
        self.assertEqual(original, "claude-opus-4-8")

        model_alias.ALIASES["strong"] = "claude-opus-4-9-hypothetical"
        try:
            repointed = model_alias.resolve_model_alias("strong")
            self.assertEqual(
                repointed,
                "claude-opus-4-9-hypothetical",
                "resolve_model_alias must reflect the patched ALIASES value",
            )
        finally:
            model_alias.ALIASES["strong"] = "claude-opus-4-8"


class TestResolveNonStrInputPassesThrough(unittest.TestCase):
    """Finding 1 (A03): resolve_model_alias must be total — non-str inputs pass through."""

    def test_list_input_passes_through(self):
        """Unhashable list must not raise TypeError (fail-soft passthrough)."""
        from model_alias import resolve_model_alias
        result = resolve_model_alias([1, 2])
        self.assertEqual(result, [1, 2])

    def test_none_input_passes_through(self):
        from model_alias import resolve_model_alias
        self.assertIsNone(resolve_model_alias(None))

    def test_int_input_passes_through(self):
        from model_alias import resolve_model_alias
        self.assertEqual(resolve_model_alias(123), 123)


class TestModelsJsonShapeIsStrStr(unittest.TestCase):
    """Finding 2 (A05): models.json must parse as dict[str, str] — CI guard."""

    def test_models_json_is_dict_of_str_to_str(self):
        import json
        data = json.loads(MODELS_JSON.read_text())
        self.assertIsInstance(data, dict, "models.json must be a JSON object (dict)")
        for key, value in data.items():
            self.assertIsInstance(
                key, str,
                f"models.json key {key!r} is not a str — every key must be str",
            )
            self.assertIsInstance(
                value, str,
                f"models.json value for key {key!r} is {value!r}, expected str",
            )


if __name__ == "__main__":
    unittest.main()
