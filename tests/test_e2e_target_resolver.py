"""C3 — e2e_target_resolver: target detection, glob mitigations, verdict composition.

Covers AC7-AC19 (resolver core), AC30/AC31 (H1 glob mitigations: top-level
files + brace expansion), AC34 (M4 both-configs preference), AC35 (M5
small-suite no-carve-out flake gate).

The resolver lives in `hooks/_lib/e2e_target_resolver.py`. Tests assert
public surface: `detect_targets`, `compose_verdict`,
`coerce_web_status_for_flake`, `select_web_driver`, plus the
`SCREENSHOT_PATH_TEMPLATE`, `WEB_FLAKE_THRESHOLD`, and
`PER_TARGET_STATUS_ENUM` constants.
"""
import tempfile
import unittest
from pathlib import Path

import e2e_target_resolver as r


def _mk_project(tmpdir, *, maestro=False, playwright=False, cypress=False):
    root = Path(tmpdir)
    if maestro:
        (root / "maestro").mkdir()
    if playwright:
        (root / "playwright.config.ts").write_text("")
    if cypress:
        (root / "cypress.config.js").write_text("")
    return root


# ---------------- AC7-AC11: target detection ----------------


class DetectTargets(unittest.TestCase):
    def test_detects_web_only_when_web_globs_match_and_playwright_config_exists(self):
        """AC7: web glob match + playwright.config.ts → web fires, mobile=N/A."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, playwright=True)
            result = r.detect_targets(["src/login/AuthForm.tsx"], root)
            self.assertEqual(result["web"], "FIRED")
            self.assertEqual(result["mobile"], "N/A")

    def test_detects_mobile_only_when_mobile_globs_match_and_maestro_dir_exists(self):
        """AC8: mobile glob + maestro/ → mobile fires, web=N/A."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, maestro=True)
            result = r.detect_targets(["app/_layout.tsx"], root)
            self.assertEqual(result["mobile"], "FIRED")
            self.assertEqual(result["web"], "N/A")

    def test_detects_both_when_both_match(self):
        """AC9: both glob types + both configs → both fire (no short-circuit)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, maestro=True, playwright=True)
            result = r.detect_targets(
                ["app/_layout.tsx", "src/login/AuthForm.tsx"], root)
            self.assertEqual(result["mobile"], "FIRED")
            self.assertEqual(result["web"], "FIRED")

    def test_web_target_skip_when_no_config_file_present(self):
        """AC10: web glob match but no playwright/cypress config → web=N/A."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp)  # no configs
            result = r.detect_targets(["src/login/AuthForm.tsx"], root)
            self.assertEqual(result["web"], "N/A")

    def test_cypress_config_alternative_satisfies_web_target(self):
        """AC11: cypress.config.js alone is sufficient for web target."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, cypress=True)
            result = r.detect_targets(["src/login/AuthForm.tsx"], root)
            self.assertEqual(result["web"], "FIRED")


# ---------------- AC12, AC13: constants ----------------


class Constants(unittest.TestCase):
    def test_screenshot_path_template_constant(self):
        """AC12: screenshot path template matches intake invariant verbatim."""
        self.assertEqual(
            r.SCREENSHOT_PATH_TEMPLATE,
            "pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/")

    def test_web_flake_threshold_constant(self):
        """AC13: flake threshold is 0.05 (5%)."""
        self.assertEqual(r.WEB_FLAKE_THRESHOLD, 0.05)


# ---------------- AC14, AC15: flake gate ----------------


class FlakeGate(unittest.TestCase):
    def test_flake_rate_above_threshold_fails_target(self):
        """AC14: flake=0.07 → web coerced to FAIL → composite UNVERIFIED."""
        coerced = r.coerce_web_status_for_flake({"web": "PASS"}, 0.07)
        self.assertEqual(coerced["web"], "FAIL")
        self.assertEqual(r.compose_verdict(coerced), "UNVERIFIED")

    def test_flake_rate_at_or_below_threshold_passes_target(self):
        """AC15: strict `>` gate — flake=0.05 (boundary) leaves PASS unchanged."""
        coerced = r.coerce_web_status_for_flake({"web": "PASS"}, 0.05)
        self.assertEqual(coerced["web"], "PASS")


# ---------------- AC16-AC19: composite verdict ----------------


class ComposeVerdict(unittest.TestCase):
    def test_composite_verdict_any_fail_is_unverified(self):
        """AC16: any FAIL → UNVERIFIED."""
        self.assertEqual(
            r.compose_verdict({"mobile": "PASS", "web": "FAIL"}),
            "UNVERIFIED")

    def test_composite_verdict_any_skip_with_no_fail_is_verified_with_skip(self):
        """AC17: any SKIP and no FAILs → VERIFIED_WITH_SKIP."""
        self.assertEqual(
            r.compose_verdict({"mobile": "PASS", "web": "SKIP"}),
            "VERIFIED_WITH_SKIP")

    def test_composite_verdict_all_pass_is_verified(self):
        """AC18: all PASS → VERIFIED."""
        self.assertEqual(
            r.compose_verdict({"mobile": "PASS", "web": "PASS"}),
            "VERIFIED")

    def test_composite_verdict_all_na_is_verified(self):
        """AC19: all N/A → VERIFIED."""
        self.assertEqual(
            r.compose_verdict({"mobile": "N/A", "web": "N/A"}),
            "VERIFIED")


# ---------------- AC30, AC31: H1 glob mitigations ----------------


class GlobMitigations(unittest.TestCase):
    def test_top_level_file_matches_double_star_prefix_pattern(self):
        """AC30 (H1): `middleware.ts` (top-level) matches pattern `**/middleware.ts`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, playwright=True)
            result = r.detect_targets(["middleware.ts"], root)
            self.assertEqual(result["web"], "FIRED",
                             "Top-level `middleware.ts` must match `**/middleware.ts`")

    def test_brace_expansion_pattern_matches_each_extension(self):
        """AC31 (H1): `**/sw.{js,ts}` brace-expands and matches both extensions."""
        # Sibling assertion on the helper.
        self.assertEqual(
            sorted(r._expand_braces("**/sw.{js,ts}")),
            sorted(["**/sw.js", "**/sw.ts"]))
        # Integration: src/sw.ts must trigger web target.
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, playwright=True)
            result = r.detect_targets(["src/sw.ts"], root)
            self.assertEqual(result["web"], "FIRED",
                             "Brace-expanded `**/sw.{js,ts}` must match `src/sw.ts`")


# ---------------- AC34 (M4): both-configs preference ----------------


class DriverSelection(unittest.TestCase):
    def test_both_configs_present_prefers_playwright_and_logs_warning(self):
        """AC34 (M4): both configs → driver=playwright + warning emitted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, playwright=True, cypress=True)
            result = r.select_web_driver(root)
            self.assertEqual(result["driver"], "playwright")
            warning = result.get("warning") or ""
            self.assertIn("playwright", warning.lower())
            self.assertIn("cypress", warning.lower())

    def test_only_playwright_config_returns_playwright_no_warning(self):
        """Playwright alone → driver=playwright, no warning."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, playwright=True)
            result = r.select_web_driver(root)
            self.assertEqual(result["driver"], "playwright")
            self.assertFalse(result.get("warning"))

    def test_only_cypress_config_returns_cypress_no_warning(self):
        """Cypress alone → driver=cypress, no warning."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp, cypress=True)
            result = r.select_web_driver(root)
            self.assertEqual(result["driver"], "cypress")
            self.assertFalse(result.get("warning"))

    def test_no_config_returns_none(self):
        """No configs → driver=None."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _mk_project(tmp)
            result = r.select_web_driver(root)
            self.assertIsNone(result["driver"])


# ---------------- AC35 (M5): small-suite flake gate (no carve-out) ----------------


class SmallSuiteFlakeGate(unittest.TestCase):
    def test_flake_gate_fires_at_small_suite_size_no_carve_out(self):
        """AC35 (M5): 1 retry in 19 tests → flake_rate ≈ 0.0526 → web=FAIL."""
        flake_rate = 1 / 19  # ≈ 0.0526
        self.assertGreater(flake_rate, r.WEB_FLAKE_THRESHOLD)
        coerced = r.coerce_web_status_for_flake({"web": "PASS"}, flake_rate)
        self.assertEqual(coerced["web"], "FAIL",
                         "Small-suite flake_rate > 0.05 must downgrade web to FAIL")

    def test_zero_retries_in_small_suite_unchanged(self):
        """AC35 (sibling): 0 retries → flake_rate = 0 → web stays PASS."""
        coerced = r.coerce_web_status_for_flake({"web": "PASS"}, 0.0)
        self.assertEqual(coerced["web"], "PASS")


if __name__ == "__main__":
    unittest.main()
