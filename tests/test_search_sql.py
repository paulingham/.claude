"""Search SQL templates — opaque strings, sanity-check placeholders."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import search_sql  # noqa: E402


class Placeholders(unittest.TestCase):
    def test_obs_template_contains_priv_and_where_placeholders(self):
        self.assertIn("{priv}", search_sql.OBS)
        self.assertIn("{where}", search_sql.OBS)

    def test_sp_template_contains_priv_and_where_placeholders(self):
        self.assertIn("{priv}", search_sql.SP)
        self.assertIn("{where}", search_sql.SP)


if __name__ == "__main__":
    unittest.main()
