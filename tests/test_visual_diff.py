"""Tier 1 unit tests for slice-a-pixel-diff-pump — Python-checkable surface.

These tests cover behaviors that can be asserted without spawning Playwright
or running JS code: SKILL.md documentation contracts, shell helper outputs
on synthetic inputs, and Python-side parsing of the project CLAUDE.md
`## Visual Regression` YAML block.

Tier 1 JS unit tests for `hooks/_lib/visual_diff.js` live in
`tests/test_visual_diff.js` (node:test runner).
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN_QC_SKILL = ROOT / "skills" / "design-qc" / "SKILL.md"
BASELINE_CAPTURE_SH = ROOT / "hooks" / "_lib" / "baseline_capture.sh"
VISUAL_DIFF_JS = ROOT / "hooks" / "_lib" / "visual_diff.js"


def _read(path):
    return path.read_text(encoding="utf-8")


class BaselineCaptureCreatesPngsUnderVisualBaselinesDir(unittest.TestCase):
    """AC1: baseline_capture.sh writes baselines under
    `pipeline-state/{task-id}/visual-baselines/`."""

    def test_baseline_capture_creates_pngs_under_visual_baselines_dir(self):
        """SKILL.md documents the baseline path contract.

        Behavioural verification of an actual `git worktree add` + build cycle
        is Tier 2 (integration) — see plan § 6. At Tier 1 we assert the
        helper documents and resolves to the canonical path.
        """
        body = _read(BASELINE_CAPTURE_SH)
        # Path contract: must reference the visual-baselines directory.
        self.assertRegex(
            body,
            r"pipeline-state/[^/]+/visual-baselines",
            "baseline_capture.sh must write to pipeline-state/{task-id}/visual-baselines/",
        )


class BaselineBuildFailedTreatsAllRoutesAsAutoBlessed(unittest.TestCase):
    """AC1 / failure-mode-1: when baseline build on main HEAD fails, all
    routes are treated as auto-bless and `visual_regression.captured: false`."""

    def test_baseline_build_failed_treats_all_routes_as_auto_blessed(self):
        body = _read(BASELINE_CAPTURE_SH)
        # Failure-mode handling must be documented in the helper.
        self.assertIn(
            "baseline-build-failed",
            body,
            "baseline_capture.sh must emit `baseline-build-failed` scratchpad warning",
        )


class PlaywrightToHaveScreenshotWritesPixelDiffRatioToIndexJson(unittest.TestCase):
    """AC2: design-qc SKILL.md documents that Playwright `toHaveScreenshot`
    writes per-route `pixel_diff_ratio` into index.json."""

    def test_skill_md_documents_pixel_diff_ratio_in_index_json(self):
        body = _read(DESIGN_QC_SKILL)
        # The schema must document where pixel_diff_ratio nests in index.json:
        # `routes`, `visual_regression`, and `pixel_diff_ratio` must all appear.
        # The Visual Regression block (in the index.json schema section) must
        # name both `routes` and `pixel_diff_ratio` in proximity.
        self.assertIn("pixel_diff_ratio", body)
        self.assertIn("routes", body)
        self.assertIn("visual_regression", body)
        # Strong-form: find the JSON code block that documents the per-route
        # nesting. The block must contain both `routes` and `pixel_diff_ratio`.
        block_idx = body.find('"visual_regression"')
        self.assertGreater(
            block_idx,
            -1,
            "SKILL.md must include a JSON example of the visual_regression block",
        )
        # The JSON block extends to the next ``` fence after this marker.
        end_fence = body.find("```", block_idx)
        block = body[block_idx:end_fence] if end_fence > 0 else body[block_idx:]
        self.assertIn("routes", block)
        self.assertIn("pixel_diff_ratio", block)


class ScreenshotsLandAtClaudeScreenshotsNotPlaywrightDefault(unittest.TestCase):
    """AC2 / SE-5 / failure-mode-9: screenshot artifacts land at
    `.claude/screenshots/`, NOT Playwright's default `__screenshots__/`."""

    def test_skill_md_overrides_playwright_default_snapshot_dir(self):
        body = _read(DESIGN_QC_SKILL)
        # Override directive must be present and explicit.
        self.assertIn(".claude/screenshots", body)
        self.assertIn("snapshotDir", body)
        # The override should appear in proximity to the Playwright block.
        playwright_start = body.find("Playwright")
        self.assertGreater(
            playwright_start, -1, "SKILL.md must reference Playwright (AC2 port)"
        )
        # Look for snapshotDir AFTER the first Playwright mention.
        snapshot_dir_idx = body.find("snapshotDir", playwright_start)
        self.assertGreater(
            snapshot_dir_idx, -1, "snapshotDir override must appear in/after Playwright block"
        )


class PlaywrightNullResultWritesPixelDiffRatio10WithFragilityScratchpad(unittest.TestCase):
    """AC2 / failure-mode-2: when Playwright returns null diff, per-route
    `pixel_diff_ratio: 1.0` is written and `playwright-null-diff-{route}` scratchpad."""

    def test_skill_md_documents_playwright_null_diff_fallback(self):
        body = _read(DESIGN_QC_SKILL)
        # Failure-mode token must be documented for breadcrumb tracing.
        self.assertIn(
            "playwright-null-diff",
            body,
            "SKILL.md must document the `playwright-null-diff-{route}` fragility token",
        )


class FrontendGlobExtensionIncludesHtmlFileChanges(unittest.TestCase):
    """AC5: frontend-touching glob extended to include `.html`."""

    def test_skill_md_when_to_invoke_lists_html_extension(self):
        body = _read(DESIGN_QC_SKILL)
        when_block_start = body.find("## When to Invoke")
        next_section = body.find("\n## ", when_block_start + 1)
        when_block = body[when_block_start:next_section]
        self.assertIn(".html", when_block, "AC5: When to Invoke must list `.html`")
        # Also keep existing extensions to avoid regression.
        for ext in (".tsx", ".jsx", ".vue", ".svelte"):
            self.assertIn(
                ext, when_block, f"AC5 regression: existing extension {ext} must remain"
            )


class NewRouteAutoBlessedWritesScratchpadWarningWithLiteralToken(unittest.TestCase):
    """AC6: route present on branch but absent on main → auto-bless +
    scratchpad warning with literal token `auto-blessed-baseline`."""

    def test_skill_md_documents_auto_blessed_baseline_scratchpad(self):
        body = _read(DESIGN_QC_SKILL)
        # Literal token MUST appear (programmatic breadcrumb).
        self.assertIn("auto-blessed-baseline", body)
        # Token must be in the context of scratchpad/warning.
        token_idx = body.find("auto-blessed-baseline")
        window = body[max(0, token_idx - 400) : token_idx + 100]
        self.assertRegex(
            window,
            r"scratchpad|category:\s*warning",
            "auto-blessed-baseline must be documented as a scratchpad warning",
        )


class PerRouteThresholdAboveDefaultDoesNotTripGlobalThreshold(unittest.TestCase):
    """AC7: per-route threshold of 0.05 with measured diff 0.04 does not
    trigger the global 0.02 threshold."""

    def test_skill_md_documents_per_route_threshold_precedence(self):
        body = _read(DESIGN_QC_SKILL)
        # Per-route override must be documented as taking precedence over default.
        self.assertIn("per_route", body)
        self.assertIn("0.02", body, "Default threshold 0.02 must be documented")
        # Precedence semantic: per-route consulted FIRST, default is fallback.
        # The harness convention is to document this in the section near the
        # threshold field.
        threshold_idx = body.find("per_route")
        window = body[max(0, threshold_idx - 200) : threshold_idx + 500]
        self.assertRegex(
            window,
            r"default|fallback|override|precedence|first",
            "per_route precedence over default must be explicitly documented",
        )


class ProjectClaudeMdPerRouteThresholdOverrideHonored(unittest.TestCase):
    """AC7: project .claude/CLAUDE.md `## Visual Regression` YAML with
    per_route overrides specific routes; absence falls back to default 0.02."""

    def test_skill_md_documents_visual_regression_section_schema(self):
        body = _read(DESIGN_QC_SKILL)
        self.assertIn("## Visual Regression", body)
        # Schema must document `default_max_diff_pixel_ratio` and `per_route`.
        # Match the actual section header (line-anchored) to skip inline text
        # references in earlier prose.
        section = self._extract_section(body, "## Visual Regression")
        self.assertRegex(
            section,
            r"default_max_diff_pixel_ratio",
            "## Visual Regression must document `default_max_diff_pixel_ratio`",
        )
        self.assertIn("per_route", section)

    def test_skill_md_documents_missing_section_fallback_to_default(self):
        body = _read(DESIGN_QC_SKILL)
        section = self._extract_section(body, "## Visual Regression")
        # Absence of the section must fall back to default — documented invariant.
        self.assertRegex(
            section,
            r"(missing|absent|absence|no section)",
            "## Visual Regression must document missing-section behaviour",
        )

    @staticmethod
    def _extract_section(body, header):
        # Find the LINE-ANCHORED section header so we skip inline prose
        # references that happen to mention `## Visual Regression` in
        # narrative text. Returns the slice up to the next `##` header.
        marker = "\n" + header + "\n"
        idx = body.find(marker)
        if idx < 0:
            # Tolerate header at file start.
            if body.startswith(header + "\n"):
                idx = 0
                start = len(header) + 1
            else:
                return ""
        else:
            start = idx + len(marker)
        end = body.find("\n## ", start)
        if end < 0:
            end = len(body)
        return body[start:end]


class VisualDiffJsRunsUnderNodeTest(unittest.TestCase):
    """Smoke test: invoking `node tests/test_visual_diff.js` exits 0.

    This is the Python-side proof that the JS test file actually passes.
    Skipped automatically if node is not available in the test env.
    """

    def test_node_test_visual_diff_passes(self):
        node = self._which_node()
        if not node:
            self.skipTest("node binary not available; JS tier-1 runs separately")
        test_path = ROOT / "tests" / "test_visual_diff.js"
        if not test_path.exists():
            self.fail(f"{test_path} missing — Tier 1 JS test stub not present")
        # Run node --test for built-in runner. node 18+ supports --test.
        env = os.environ.copy()
        result = subprocess.run(
            [node, "--test", str(test_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        if result.returncode != 0:
            self.fail(
                "tests/test_visual_diff.js failed:\n"
                f"--- stdout ---\n{result.stdout}\n"
                f"--- stderr ---\n{result.stderr}"
            )

    @staticmethod
    def _which_node():
        # Check $PATH for node; respect nvm if invoking shell.
        from shutil import which

        candidate = which("node")
        if candidate:
            return candidate
        # Common nvm locations the bash test runners use.
        for guess in (
            os.path.expanduser("~/.nvm/versions/node/v24.14.0/bin/node"),
            os.path.expanduser("~/.nvm/versions/node/*/bin/node"),
        ):
            if "*" not in guess and os.path.exists(guess):
                return guess
        return None


if __name__ == "__main__":
    unittest.main()
