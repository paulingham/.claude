"""Re-export of pipeline_frontmatter.parse_frontmatter for test API stability.

The advisor resolver originally shipped a parallel implementation; review
collapsed it to a single source of truth in pipeline_frontmatter to eliminate
the duplication. Existing imports `from advisor_frontmatter import
parse_frontmatter` continue to work unchanged.
"""
from pipeline_frontmatter import parse_frontmatter  # noqa: F401
