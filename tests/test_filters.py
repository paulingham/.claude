"""Filter whitelist: parameterised WHERE fragments per source scope."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import filters  # noqa: E402


class ObservationFilters(unittest.TestCase):
    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            filters.resolve("observations", {"secret_sql": "x"})

    def test_unknown_key_error_does_not_echo_attacker_string(self):
        try:
            filters.resolve("observations",
                            {"\x1b[2Jhack": "x", "other": "y"})
        except ValueError as exc:
            msg = str(exc)
            self.assertNotIn("\x1b", msg)
            self.assertNotIn("hack", msg)

    def test_known_keys_emit_binds(self):
        where, params = filters.resolve(
            "observations", {"session_id": "s1", "tool": "Read"})
        self.assertIn("session_id = ?", where)
        self.assertIn("tool = ?", where)
        self.assertEqual(params, ("s1", "Read"))


class ScratchpadFilters(unittest.TestCase):
    def test_scratchpad_scope_keys(self):
        where, _ = filters.resolve(
            "scratchpad", {"task_id": "t1", "category": "warning"})
        self.assertIn("task_id = ?", where)
        self.assertIn("category = ?", where)


if __name__ == "__main__":
    unittest.main()
