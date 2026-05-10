"""Slice slice-a-schema-spec: agents/architect.md documents Artifact 5 — Slice DAG.

Three ACs from pipeline-state/architect-plan-dag/plan.md:

- AC1: agents/architect.md contains `### Artifact 5 — Slice DAG` after Artifact 4,
  specifying YAML codeblock with `id`, `depends-on`, `description` REQUIRED and
  `domain` OPTIONAL.
- AC2: Plan Output Contract documents `schema_version: 2` frontmatter, validation
  rules 1-7, DUAL_PATH soak window (90 days, ends 2026-08-08), and v1-bypasses-helper.
- AC3: v2 stubs group under `### Slice <id>` headings; v1 retains flat layout.

These tests are markdown-grep style — they assert documentation completeness, not
executable behaviour. The architect.md file is the contract for every Plan-phase
spawn, so its content IS the specification.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHITECT_MD = REPO_ROOT / "agents" / "architect.md"


def _read_architect_md() -> str:
    return ARCHITECT_MD.read_text()


def _section_body(heading: str, text: str) -> str:
    """Return the body following an exact `###` heading line, up to the next
    same-or-higher-level heading. Returns empty string if heading is absent."""
    pattern = rf"^{re.escape(heading)}\s*$(.*?)(?=^##\s|^###\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


class Artifact5SliceDagSection(unittest.TestCase):
    """AC1 — section presence and field structure."""

    def test_artifact_5_slice_dag_section_exists(self):
        text = _read_architect_md()
        # Heading appears after Artifact 4. Use line-anchored search to avoid
        # accidental substring matches inside prose.
        artifact_4_idx = text.find("### Artifact 4")
        artifact_5_idx = text.find("### Artifact 5 — Slice DAG")
        self.assertGreater(
            artifact_5_idx, -1,
            "agents/architect.md must contain `### Artifact 5 — Slice DAG` heading",
        )
        self.assertGreater(
            artifact_5_idx, artifact_4_idx,
            "Artifact 5 must appear AFTER Artifact 4 (insertion order matters)",
        )

    def test_artifact_5_yaml_block_documents_required_fields(self):
        text = _read_architect_md()
        body = _section_body("### Artifact 5 — Slice DAG", text)
        self.assertTrue(body, "Artifact 5 section body must be non-empty")

        # Required fields must be named explicitly with REQUIRED marker
        for field in ("id", "depends-on", "description"):
            self.assertRegex(
                body,
                rf"\b{re.escape(field)}\b.*\bREQUIRED\b",
                f"Artifact 5 must document `{field}` as REQUIRED",
            )

        # `domain` must be named as OPTIONAL
        self.assertRegex(
            body,
            r"\bdomain\b.*\bOPTIONAL\b",
            "Artifact 5 must document `domain` as OPTIONAL",
        )

        # YAML codeblock must be present (the helper parses it as fenced YAML)
        self.assertIn(
            "```yaml",
            body,
            "Artifact 5 must include a fenced ```yaml codeblock so the helper "
            "parses it unambiguously",
        )
        # Codeblock must contain the slices: list anchor
        self.assertIn(
            "slices:",
            body,
            "Artifact 5 YAML codeblock must show the `slices:` list anchor",
        )


class SchemaVersion2DocumentedInPlanOutputContract(unittest.TestCase):
    """AC2 — schema_version: 2 + validation rules 1-7 + DUAL_PATH soak documented."""

    def test_schema_version_2_documented_in_plan_output_contract(self):
        text = _read_architect_md()

        # The Plan Output Contract section must mention schema_version: 2 + dag: true
        self.assertIn(
            "schema_version: 2",
            text,
            "Plan Output Contract must document `schema_version: 2` discriminator",
        )
        self.assertIn(
            "dag: true",
            text,
            "Plan Output Contract must document the `dag: true` capability flag",
        )

        # All 7 validation rules must appear by name (canonical error tokens
        # from the plan: cycle, dangling, self-dep, bad-id-format/kebab-case,
        # duplicate-ids, empty plan, empty-description).
        rule_tokens = [
            "cycle",            # Rule 1 — no cycles
            "dangling",         # Rule 2 — depends-on IDs declared
            "self-dep",         # Rule 3 — no self-deps
            "kebab-case",       # Rule 4 — kebab-case IDs
            "duplicate-ids",    # Rule 5 — uniqueness
            "empty plan",       # Rule 6 — non-empty slices list
            "empty-description",  # Rule 7 — non-empty description
        ]
        for token in rule_tokens:
            self.assertIn(
                token, text,
                f"Plan Output Contract must document validation rule token "
                f"`{token}` (one of the 7 canonical rules)",
            )

        # DUAL_PATH soak: 90-day window + soak-end calendar anchor
        self.assertIn(
            "90", text,
            "Plan Output Contract must document the 90-day DUAL_PATH soak window",
        )
        self.assertIn(
            "2026-08-08", text,
            "Plan Output Contract must document the soak-end calendar anchor "
            "(2026-08-08, 90 days from merge)",
        )

        # v1-bypasses-helper semantics: v1 plans are dispatched via the legacy
        # path; the helper is v2-only.
        self.assertRegex(
            text,
            r"v1.*(bypass|legacy|v2-only)",
            "Plan Output Contract must document v1-bypasses-helper semantics "
            "(v1 plans dispatched via legacy path; helper is v2-only)",
        )


class PerSliceStubGroupingDocumented(unittest.TestCase):
    """AC3 — v2 groups stubs under `### Slice <id>` headings; v1 retains flat."""

    def test_per_slice_stub_grouping_documented(self):
        text = _read_architect_md()

        # The grouping rule must be stated explicitly.
        self.assertRegex(
            text,
            r"### Slice <id>",
            "Plan Output Contract must specify v2 stubs group under "
            "`### Slice <id>` headings",
        )

        # v1 retains flat layout — must be stated explicitly so emitters
        # do not retrofit the v2 grouping onto legacy plans.
        self.assertRegex(
            text,
            r"v1.*\bflat\b",
            "Plan Output Contract must state that v1 plans retain the "
            "flat per-AC stub layout",
        )


if __name__ == "__main__":
    unittest.main()
