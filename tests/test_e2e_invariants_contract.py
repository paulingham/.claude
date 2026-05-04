"""C3 — Tier 0 contract assertions for the 5 intake invariants (AC24-AC28).

These pin the public surface of `e2e_target_resolver` against the verbatim
invariants from `pipeline-state/web-e2e-playwright/intake.md`. Any drift in
constants or signatures is caught here BEFORE it affects downstream skills.
"""
import inspect
import tempfile
import unittest
from pathlib import Path

import e2e_target_resolver as r


# ---------------- AC24: Tier 4 verdict enums unchanged ----------------


def test_invariant_tier4_verdict_enum_unchanged():
    """AC24: per-target enum {PASS,FAIL,SKIP,N/A}; composite VERIFIED|VERIFIED_WITH_SKIP|UNVERIFIED."""
    assert "PASS" in r.PER_TARGET_STATUS_ENUM
    assert "FAIL" in r.PER_TARGET_STATUS_ENUM
    assert "SKIP" in r.PER_TARGET_STATUS_ENUM
    assert "N/A" in r.PER_TARGET_STATUS_ENUM
    # Composite verdicts ARE the only valid outputs of compose_verdict.
    valid = {"VERIFIED", "VERIFIED_WITH_SKIP", "UNVERIFIED"}
    # Spot-check each composite is reachable from compose_verdict.
    assert r.compose_verdict({"web": "PASS"}) in valid
    assert r.compose_verdict({"web": "FAIL"}) in valid
    assert r.compose_verdict({"web": "SKIP"}) in valid
    assert r.compose_verdict({"web": "PASS"}) == "VERIFIED"
    assert r.compose_verdict({"web": "FAIL"}) == "UNVERIFIED"
    assert r.compose_verdict({"web": "SKIP"}) == "VERIFIED_WITH_SKIP"


# ---------------- AC25: screenshot path verbatim ----------------


def test_invariant_screenshot_path_string_matches_intake():
    """AC25: SCREENSHOT_PATH_TEMPLATE matches intake invariant verbatim."""
    expected = ("pipeline-state/{task_id}/scratchpad/"
                "qa-engineer-verify-screenshots/")
    assert r.SCREENSHOT_PATH_TEMPLATE == expected


# ---------------- AC26: flake gate threshold + strict `>` ----------------


def test_invariant_web_flake_gate_threshold():
    """AC26: WEB_FLAKE_THRESHOLD == 0.05 with STRICT `>` (not `>=`)."""
    assert r.WEB_FLAKE_THRESHOLD == 0.05
    # At-threshold (boundary) MUST stay PASS — strict `>`.
    coerced = r.coerce_web_status_for_flake({"web": "PASS"}, 0.05)
    assert coerced["web"] == "PASS", \
        "Strict `>` gate violated: flake_rate == threshold downgraded to FAIL"
    # Just above threshold MUST fail.
    coerced = r.coerce_web_status_for_flake({"web": "PASS"}, 0.0501)
    assert coerced["web"] == "FAIL"


# ---------------- AC27: independent matchers (no short-circuit) ----------------


def test_invariant_both_targets_can_fire_independently():
    """AC27: detect_targets does not short-circuit — both can fire on one diff."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "maestro").mkdir()
        (root / "playwright.config.ts").write_text("")
        result = r.detect_targets(
            ["app/_layout.tsx", "src/login/AuthForm.tsx"], root)
        assert result["mobile"] == "FIRED"
        assert result["web"] == "FIRED"


# ---------------- AC28: shared status enum across targets ----------------


def test_invariant_shared_verdict_enum_across_targets():
    """AC28: both targets read from PER_TARGET_STATUS_ENUM (same shape)."""
    assert isinstance(r.PER_TARGET_STATUS_ENUM, frozenset)
    assert r.PER_TARGET_STATUS_ENUM == frozenset(
        {"PASS", "FAIL", "SKIP", "N/A"})
    # compose_verdict must accept the same enum for ALL keys.
    # Mixing valid statuses (mobile + web) must not raise.
    r.compose_verdict({"mobile": "PASS", "web": "FAIL"})
    r.compose_verdict({"mobile": "SKIP", "web": "N/A"})


# ---------------- API signatures (Tier 0 spec lock) ----------------


class APISignatures(unittest.TestCase):
    def test_compose_verdict_signature(self):
        sig = inspect.signature(r.compose_verdict)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["target_results"])

    def test_coerce_web_status_for_flake_signature(self):
        sig = inspect.signature(r.coerce_web_status_for_flake)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["target_results", "flake_rate"])

    def test_compose_verdict_raises_on_invalid_status(self):
        """Tier 0 contract: invalid status → ValueError."""
        with self.assertRaises(ValueError):
            r.compose_verdict({"web": "BOGUS"})
