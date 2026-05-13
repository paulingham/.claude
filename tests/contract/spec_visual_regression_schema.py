"""Slice slice-a-pixel-diff-pump — Tier 0 contract tests.

Asserts:
  1. `skills/design-qc/SKILL.md` declares `schema_version: 2` for index.json.
  2. `skills/design-qc/SKILL.md` documents the `visual_regression` block
     shape (`captured`, per-route `pixel_diff_ratio`, `baseline_path`).
  3. `hooks/_lib/visual_diff.js` exists and declares the typed signature
     `computePixelDiffRatio(baseline: Buffer, current: Buffer, threshold: number) -> number`.
  4. The Playwright snapshot dir override (`.claude/screenshots/`) is named
     verbatim in `skills/design-qc/SKILL.md` Step 6.
  5. The soak-end placeholder file at
     `pipeline-state/vlm-spec-blind-common-extract-soak-end/pipeline.md`
     exists with frontmatter `not_before: 2026-06-09T00:00:00Z` and body
     naming BOTH clone files as consolidation targets.

Contract tests run as pure-Python assertions against source-tree artifacts;
they do NOT spawn Playwright, Node, or external test runners. Behavioural
verification of pixel-diff math lives in Tier 1 unit tests in
`tests/test_visual_diff.py`.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DESIGN_QC_SKILL = ROOT / "skills" / "design-qc" / "SKILL.md"
VISUAL_DIFF_JS = ROOT / "hooks" / "_lib" / "visual_diff.js"
BASELINE_CAPTURE_SH = ROOT / "hooks" / "_lib" / "baseline_capture.sh"
SOAK_PLACEHOLDER = (
    ROOT
    / "pipeline-state"
    / "vlm-spec-blind-common-extract-soak-end"
    / "pipeline.md"
)


def _read(path):
    return path.read_text(encoding="utf-8")


class IndexJsonSchemaV2(unittest.TestCase):
    """AC1/AC2 — schema_version bumped 1 -> 2 in design-qc/SKILL.md."""

    def test_design_qc_skill_declares_schema_version_2(self):
        self.assertTrue(DESIGN_QC_SKILL.exists(), "design-qc/SKILL.md missing")
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(
            "schema_version: 2",
            body,
            "design-qc/SKILL.md must declare schema_version: 2 for index.json",
        )

    def test_design_qc_skill_documents_visual_regression_block(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn("visual_regression", body)
        self.assertIn("pixel_diff_ratio", body)
        self.assertIn("baseline_path", body)


class VisualDiffHelperContract(unittest.TestCase):
    """AC2 — pixel-diff helper exists with typed signature documented."""

    def test_visual_diff_js_exists(self):
        self.assertTrue(
            VISUAL_DIFF_JS.exists(),
            f"{VISUAL_DIFF_JS} must exist (AC2 pixel-diff helper)",
        )

    def test_visual_diff_declares_typed_signature(self):
        body = _read(VISUAL_DIFF_JS)
        # Typed-signature comment is the harness convention for JS helpers.
        self.assertIn("computePixelDiffRatio", body)
        self.assertIn("baseline", body)
        self.assertIn("current", body)
        self.assertIn("threshold", body)

    def test_visual_diff_exports_compute_pixel_diff_ratio(self):
        body = _read(VISUAL_DIFF_JS)
        # CommonJS export shape (matches harness JS-helper convention at
        # hooks/_lib/a11y_normalize.js and similar).
        self.assertRegex(
            body,
            r"module\.exports\s*=\s*\{[^}]*computePixelDiffRatio",
            "visual_diff.js must export computePixelDiffRatio via module.exports",
        )


class BaselineCaptureHelperContract(unittest.TestCase):
    """AC1 — baseline_capture.sh exists as the Step 5.5 helper."""

    def test_baseline_capture_sh_exists(self):
        self.assertTrue(
            BASELINE_CAPTURE_SH.exists(),
            f"{BASELINE_CAPTURE_SH} must exist (AC1 baseline-capture helper)",
        )

    def test_baseline_capture_sh_uses_git_worktree_add(self):
        body = _read(BASELINE_CAPTURE_SH)
        # AC1 contract: baseline capture uses `git worktree add`, NOT bare checkout.
        self.assertIn(
            "git worktree add",
            body,
            "baseline_capture.sh must use `git worktree add` per Iron Law 4",
        )

    def test_baseline_capture_sh_writes_to_visual_baselines_dir(self):
        body = _read(BASELINE_CAPTURE_SH)
        self.assertIn("visual-baselines", body)


class PlaywrightOutputDirOverride(unittest.TestCase):
    """AC2 / SE-5 / failure-mode-9 — Playwright config explicitly overrides
    default snapshot dir to `.claude/screenshots/`."""

    def test_skill_md_declares_snapshot_dir_override(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(".claude/screenshots", body)
        # Path-contract preservation: the override must be in the Playwright
        # block, not just a leftover Puppeteer reference.
        self.assertIn("snapshotDir", body)

    def test_skill_md_no_underscore_screenshots_default_referenced_as_target(self):
        body = _read(DESIGN_QC_SKILL)
        # The default `__screenshots__/` may be MENTIONED (as the thing we're
        # overriding) but must NOT be the configured target. Sanity check:
        # `.claude/screenshots` should appear at least as often as the default.
        default_hits = body.count("__screenshots__")
        override_hits = body.count(".claude/screenshots")
        self.assertGreaterEqual(
            override_hits,
            max(1, default_hits),
            "design-qc/SKILL.md must configure `.claude/screenshots/`, not Playwright's default",
        )


class PlaywrightPortedFromPuppeteer(unittest.TestCase):
    """AC2 — Step 6 ported from Puppeteer to Playwright."""

    def test_skill_md_references_playwright_toHaveScreenshot(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(
            "toHaveScreenshot",
            body,
            "Step 6 must use Playwright `toHaveScreenshot` (AC2)",
        )

    def test_skill_md_does_not_use_puppeteer_launch_in_step_6(self):
        body = _read(DESIGN_QC_SKILL)
        # Puppeteer-launch is the previous-step-6 idiom. After port, it must
        # not appear as the primary screenshot driver in Step 6's body.
        # Tolerance: a comment naming Puppeteer as the prior state is fine.
        # Hard rule: no `puppeteer.launch` call site.
        self.assertNotIn(
            "puppeteer.launch",
            body,
            "Step 6 Puppeteer call site must be replaced by Playwright (AC2)",
        )


class HtmlGlobExtension(unittest.TestCase):
    """AC5 — frontend-touching glob extended to include `.html`."""

    def test_skill_md_when_to_invoke_lists_html(self):
        body = _read(DESIGN_QC_SKILL)
        # Look for `.html` in the When-to-Invoke block.
        when_block_start = body.find("## When to Invoke")
        when_block_end = body.find("##", when_block_start + 1)
        when_block = body[when_block_start:when_block_end]
        self.assertIn(
            ".html",
            when_block,
            "AC5: frontend-touching glob must include `.html`",
        )


class AutoBlessedBaselineWarning(unittest.TestCase):
    """AC6 — `auto-blessed-baseline` literal token documented for new-route path."""

    def test_skill_md_documents_auto_blessed_baseline_token(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(
            "auto-blessed-baseline",
            body,
            "AC6: design-qc/SKILL.md must document the `auto-blessed-baseline` scratchpad token",
        )


class PerRouteThresholdOverride(unittest.TestCase):
    """AC7 — per-route threshold override from project CLAUDE.md."""

    def test_skill_md_documents_visual_regression_claude_md_section(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(
            "## Visual Regression",
            body,
            "AC7: design-qc/SKILL.md must document the `## Visual Regression` project-CLAUDE.md section",
        )

    def test_skill_md_documents_default_max_diff_pixel_ratio(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn("0.02", body, "AC7: default threshold 0.02 must be documented")


class SoakEndPlaceholderContract(unittest.TestCase):
    """PR-4 — soak-end placeholder file shape (per plan § 8 + § 10 row 9)."""

    def test_soak_end_placeholder_file_exists_with_correct_not_before_anchor(self):
        self.assertTrue(
            SOAK_PLACEHOLDER.exists(),
            f"{SOAK_PLACEHOLDER} must exist (PR-4 soak-end anchor)",
        )
        body = _read(SOAK_PLACEHOLDER)
        # Frontmatter contract.
        match = re.match(r"^---\n(.*?)\n---", body, re.DOTALL)
        self.assertIsNotNone(match, "soak-end placeholder must have YAML frontmatter")
        frontmatter = match.group(1)
        self.assertIn(
            "not_before: 2026-06-09T00:00:00Z",
            frontmatter,
            "soak-end placeholder frontmatter must carry `not_before: 2026-06-09T00:00:00Z`",
        )

    def test_soak_end_placeholder_body_names_both_clone_files(self):
        body = _read(SOAK_PLACEHOLDER)
        # Body must explicitly name BOTH consolidation targets.
        self.assertIn("hooks/_lib/vlm-critic-guard-common.sh", body)
        self.assertIn("hooks/_lib/spec-blind-guard-common.sh", body)


if __name__ == "__main__":
    unittest.main()
