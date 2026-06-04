"""Opt-in live vlm-critic dispatch test — skipped by default.

This test makes a real `claude -p` invocation. It is billable at standard
model rates. It is skipped by default in CI. Set `CLAUDE_VLM_LIVE_CONTROL=1`
only in environments where model costs are acceptable.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_vlm_critic_no_diff_control import synthesize_minimal_png  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent.parent
_LIVE_ENABLED = os.environ.get("CLAUDE_VLM_LIVE_CONTROL") == "1"


@unittest.skipUnless(_LIVE_ENABLED, "opt-in only — set CLAUDE_VLM_LIVE_CONTROL=1 to run")
class VlmCriticLiveControlTest(unittest.TestCase):
    """AC7 — opt-in live vlm-critic dispatch against an identical PNG pair."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("claude") is None:
            raise unittest.SkipTest(
                "claude binary not on PATH; cannot run live control test"
            )
        if os.environ.get("CLAUDE_DISABLE_VLM_CRITIC") is not None:
            raise AssertionError(
                "CLAUDE_DISABLE_VLM_CRITIC is set — live test would prove nothing; "
                "unset it first"
            )

    def setUp(self):
        self._tmpdir = Path(tempfile.mkdtemp(prefix="vlm-live-control-"))
        self._baselines_dir = (
            self._tmpdir / "pipeline-state" / "live-control" / "visual-baselines"
        )
        self._screenshots_dir = self._tmpdir / ".claude" / "screenshots"
        self._design_qc_dir = (
            self._tmpdir / "pipeline-state" / "live-control" / "design-qc"
        )
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._design_qc_dir.mkdir(parents=True, exist_ok=True)

        png_bytes = synthesize_minimal_png(128, 64, 32, 255)
        (self._baselines_dir / "control.png").write_bytes(png_bytes)
        (self._screenshots_dir / "control.png").write_bytes(png_bytes)

        index = {
            "schema_version": 2,
            "visual_regression": {
                "captured": True,
                "baselines_dir": str(self._baselines_dir),
            },
            "routes": [
                {
                    "route": "/control",
                    "visual_regression": {
                        "baseline_path": str(self._baselines_dir / "control.png"),
                        "current_path": str(self._screenshots_dir / "control.png"),
                        "pixel_diff_ratio": 0.0,
                    },
                }
            ],
        }
        (self._design_qc_dir / "index.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_identical_png_pair_yields_visual_diff_pass(self):
        """AC7 — identical PNG pair staged at allowlisted paths → VISUAL_DIFF_PASS."""
        index_path = str(self._design_qc_dir / "index.json")
        prompt = (
            "Read skills/vlm-critic/SKILL.md and execute the vlm-critic procedure. "
            f"The index.json for this run is at: {index_path}. "
            "Read that index.json, evaluate each route's visual_regression "
            "baseline_path vs current_path, write vlm_verdict and vlm_summary "
            "back to index.json for each route, and emit the aggregate verdict "
            "VISUAL_DIFF_PASS or VISUAL_DIFF_FAIL."
        )
        env = os.environ.copy()
        env["CLAUDE_SUBAGENT_TYPE"] = "vlm-critic"

        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
            cwd=str(ROOT),
        )
        self.assertIn(
            "VISUAL_DIFF_PASS",
            result.stdout,
            f"Expected VISUAL_DIFF_PASS; vlm_summary may indicate hallucination.\n"
            f"stdout: {result.stdout[:2000]}\nstderr: {result.stderr[:500]}",
        )


if __name__ == "__main__":
    unittest.main()
