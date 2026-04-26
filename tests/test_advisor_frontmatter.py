"""Re-export identity test for hooks/_lib/advisor_frontmatter.py.

advisor_frontmatter must re-export pipeline_frontmatter.parse_frontmatter
so a single source of truth backs both call sites. Existing imports of
`from advisor_frontmatter import parse_frontmatter` continue to work.
"""
import unittest


class ReexportsPipelineParser(unittest.TestCase):
    def test_advisor_frontmatter_parse_is_pipeline_frontmatter_parse(self):
        import advisor_frontmatter
        import pipeline_frontmatter
        self.assertIs(advisor_frontmatter.parse_frontmatter,
                      pipeline_frontmatter.parse_frontmatter)


if __name__ == "__main__":
    unittest.main()
