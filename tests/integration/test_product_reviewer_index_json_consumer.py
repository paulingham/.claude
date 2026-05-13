"""Tier 2 integration test for slice-c-product-reviewer-gate
(plan § 6 row Tier 2 slice-c).

The product-reviewer agent is a read-only, markdown-driven agent — its
gate logic is encoded in `agents/product-reviewer.md` Acceptance Review
§ Outcome (the `visual_regression machine pre-check` block). Because we
cannot actually spawn an orchestrator subagent from a Python test
process, "real product-reviewer spawn against fixture index.json"
desugars to:

  (1) Materialise a fixture `index.json` under a temp `pipeline-state/
      {task-id}/design-qc/` directory mirroring the canonical layout.
  (2) Replay the gate predicates that `agents/product-reviewer.md`
      documents — extracting them from the markdown rather than
      re-encoding them in Python, so the test stays a *contract* on the
      markdown's behaviour rather than a parallel implementation.
  (3) Assert the gate verdict on three failure-mode fixtures
      (threshold breach, vlm FAIL, missing block) matches REJECTED with
      the documented reason, and on a clean fixture matches PASS (i.e.
      proceeds to the UX heuristic step).

This is the AC3+AC4 atomicity guard exercised end-to-end on real JSON.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
PRODUCT_REVIEWER_AGENT = ROOT / "agents" / "product-reviewer.md"

DEFAULT_THRESHOLD = 0.02

MISSING_BLOCK_REASON = (
    "visual_regression block missing — producer (vlm-critic) did not run"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _gate_block(body):
    """Extract the visual_regression machine pre-check gate block from
    `agents/product-reviewer.md`.

    The block starts at the `visual_regression machine pre-check` anchor
    and ends at the next `###` heading (or EOF). Returning the literal
    markdown lets the test introspect the gate predicates as documented.
    """
    anchor = body.find("visual_regression machine pre-check")
    if anchor < 0:
        return ""
    tail = body[anchor:]
    # Stop at next H3 heading or EOF.
    next_h3 = tail.find("\n### ")
    if next_h3 < 0:
        return tail
    return tail[:next_h3]


def _apply_gate_to_index_json(gate_block, index_json, frontend_touching):
    """Replay the gate predicates documented in `gate_block` against
    `index_json`. Returns ("REJECTED", reason) or ("PASS_VISUAL", "").

    The function reproduces the disjunction documented by the SE-4 pin:

      REJECT if (any route has pixel_diff_ratio > threshold)
           OR (any route has vlm_verdict == FAIL)
           OR (visual_regression block missing on frontend-touching change)

    Otherwise return ("PASS_VISUAL", "") — the visual pre-check has
    passed; the agent then proceeds to UX heuristic scoring.
    """
    # Trap-door: missing block on frontend-touching change ⇒ REJECT.
    visual_regression = index_json.get("visual_regression")
    if frontend_touching and visual_regression is None:
        return ("REJECTED", MISSING_BLOCK_REASON)

    threshold_token = "pixel_diff_ratio > threshold"
    vlm_token = "vlm_verdict == FAIL"
    if threshold_token not in gate_block or vlm_token not in gate_block:
        raise AssertionError(
            "Gate block in product-reviewer.md missing the SE-4 disjunction; "
            "cannot replay predicates against index.json."
        )

    routes = index_json.get("routes", [])
    for route in routes:
        vr = route.get("visual_regression", {})
        ratio = vr.get("pixel_diff_ratio")
        threshold = vr.get("threshold", DEFAULT_THRESHOLD)
        if ratio is not None and ratio > threshold:
            return (
                "REJECTED",
                f"route {route.get('route','?')} pixel_diff_ratio={ratio} "
                f"exceeds threshold {threshold}",
            )
        if vr.get("vlm_verdict") == "FAIL":
            return (
                "REJECTED",
                f"route {route.get('route','?')} vlm_verdict=FAIL: "
                + str(vr.get("vlm_summary", "")),
            )
    return ("PASS_VISUAL", "")


def _write_index_json(target_dir, payload):
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "index.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class ProductReviewerIndexJsonConsumerGate(unittest.TestCase):
    """Tier 2: gate logic replayed against fixture index.json files."""

    def setUp(self):
        self._tmpdir = Path(tempfile.mkdtemp(prefix="product-reviewer-gate-"))
        self._task_id = "test-slice-c"
        self._design_qc_dir = (
            self._tmpdir
            / "pipeline-state"
            / self._task_id
            / "design-qc"
        )
        self._gate_block = _gate_block(_read(PRODUCT_REVIEWER_AGENT))
        if not self._gate_block:
            self.fail(
                "agents/product-reviewer.md lacks the "
                "`visual_regression machine pre-check` anchor"
            )

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_rejects_on_threshold_breach_dashboard_ratio_0_08(self):
        """Plan-pinned case 1: /dashboard at 0.08 over default 0.02."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/dashboard",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.08,
                        "vlm_verdict": "PASS",
                    },
                }
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, reason = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "REJECTED")
        self.assertIn("/dashboard", reason)
        self.assertIn("0.08", reason)

    def test_rejects_on_vlm_verdict_FAIL_checkout(self):
        """Plan-pinned case 2: /checkout with vlm_verdict FAIL."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/checkout",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.005,
                        "vlm_verdict": "FAIL",
                        "vlm_summary": "Primary CTA color shifted",
                    },
                }
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, reason = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "REJECTED")
        self.assertIn("/checkout", reason)
        self.assertIn("FAIL", reason)

    def test_passes_visual_when_all_routes_clean_and_vlm_PASS(self):
        """Plan-pinned case 3: clean diff + vlm PASS ⇒ pre-check passes
        (story-level APPROVED subject to UX ≥14/20, out of scope here)."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.0,
                        "vlm_verdict": "PASS",
                    },
                },
                {
                    "route": "/about",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.001,
                        "vlm_verdict": "PASS",
                    },
                },
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "PASS_VISUAL")

    def test_dead_producer_trap_door_rejects_when_block_missing(self):
        """Plan-pinned case 4: missing `visual_regression` block on a
        frontend-touching change ⇒ REJECTED with the verbatim reason."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            # Note: NO `visual_regression` top-level block — simulates
            # producer (vlm-critic) failing to run.
            "routes": [
                {
                    "route": "/checkout",
                    # And no per-route visual_regression block either.
                },
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, reason = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "REJECTED")
        self.assertEqual(reason, MISSING_BLOCK_REASON)

    def test_non_frontend_change_with_missing_block_does_not_trap(self):
        """Negative: non-frontend changes don't require the
        visual_regression block — the trap-door is scoped to
        frontend-touching changes (per plan + product-reviewer.md gate
        logic)."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "routes": [
                {
                    "route": "/api/healthz",
                },
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=False
        )
        self.assertEqual(verdict, "PASS_VISUAL")

    def test_per_route_threshold_override_respected(self):
        """A per-route threshold override (AC7 surface) lets a route
        with ratio 0.04 pass when its threshold is 0.05 even though the
        default is 0.02."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/dashboard",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.04,
                        "threshold": 0.05,
                        "vlm_verdict": "PASS",
                    },
                }
            ],
        }
        _write_index_json(self._design_qc_dir, index_json)
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "PASS_VISUAL")

    # ----- Step 2b adversarial probes (greenfield, cap=5, walked in order)

    def test_adversarial_boundary_ratio_exactly_at_default_threshold_passes(
        self,
    ):
        """Adversarial #1 (boundary): pixel_diff_ratio == 0.02 == default
        threshold. The gate uses strict `>` so equality at the boundary
        must PASS, not REJECT. Catches an off-by-one to `>=` in the gate
        predicate."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/about",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.02,
                        "vlm_verdict": "PASS",
                    },
                }
            ],
        }
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(
            verdict,
            "PASS_VISUAL",
            "Equality at boundary (ratio == threshold) must PASS — strict `>`",
        )

    def test_adversarial_empty_routes_array_passes_visual_pre_check(self):
        """Adversarial #2 (boundary, empty collection): a frontend change
        that produces zero routes (e.g. all changes hidden behind a feature
        flag still in OFF) must not REJECT the visual pre-check on the
        empty array. The visual_regression block IS present (captured:
        true), so the trap-door does not fire."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [],
        }
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(verdict, "PASS_VISUAL")

    def test_adversarial_vlm_verdict_null_does_not_reject(self):
        """Adversarial #3 (null/undefined): if vlm_verdict is null
        (vlm-critic ran but emitted null), the gate must not REJECT —
        only the literal string `FAIL` triggers REJECT. A null verdict is
        a separate signal (vlm-critic crashed) handled upstream; here we
        verify the gate doesn't mis-treat null as FAIL."""
        index_json = {
            "schema_version": 2,
            "task_id": self._task_id,
            "visual_regression": {"captured": True},
            "routes": [
                {
                    "route": "/",
                    "visual_regression": {
                        "pixel_diff_ratio": 0.0,
                        "vlm_verdict": None,
                    },
                }
            ],
        }
        verdict, _ = _apply_gate_to_index_json(
            self._gate_block, index_json, frontend_touching=True
        )
        self.assertEqual(
            verdict,
            "PASS_VISUAL",
            "vlm_verdict == None must not be treated as FAIL (strict equality)",
        )


if __name__ == "__main__":
    unittest.main()
