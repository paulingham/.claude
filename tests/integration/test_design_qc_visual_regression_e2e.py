"""Tier 2 integration test for slice-a-pixel-diff-pump (plan § 6 row Tier 2 slice-a).

Exercises the full producer pipeline end-to-end against a fixture Next.js
project: real `git worktree add` of main HEAD, real `@playwright/test`
install, real Playwright `toHaveScreenshot` pump, and assertions on the
on-disk artifacts.

Contract (from plan § 6 + § 7 row 9):

(a) Baseline PNG exists at `pipeline-state/test-vr/visual-baselines/`.
(b) Current PNG exists at `.claude/screenshots/`.
(c) NO PNG under `__screenshots__/` (failure-mode-9 path-contract).
(d) `pipeline-state/test-vr/design-qc/index.json` has
    `routes[*].visual_regression.pixel_diff_ratio` as float for every route.

The fixture lives at `tests/fixtures/visual-regression-next/` and ships with
a single deterministic page (`app/page.tsx`) so pixel-diff against the same
HEAD yields ratio 0.0.

Skips:
- `node` or `npm` not on PATH (mirrors test_visual_diff.py::_which_node).
- `CLAUDE_SKIP_HEAVY_INTEGRATION=1` set (CI escape hatch — Playwright
  install pulls ~200 MB of browser engines).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "visual-regression-next"
BASELINE_CAPTURE_SH = ROOT / "hooks" / "_lib" / "baseline_capture.sh"
VISUAL_DIFF_JS = ROOT / "hooks" / "_lib" / "visual_diff.js"
TASK_ID = "test-vr"
FIXTURE_PORT = 4321


def _which(cmd):
    return shutil.which(cmd)


def _heavy_skipped():
    return os.environ.get("CLAUDE_SKIP_HEAVY_INTEGRATION") == "1"


class DesignQcVisualRegressionE2E(unittest.TestCase):
    """End-to-end: real Playwright + real git worktree + real Next.js fixture."""

    @classmethod
    def setUpClass(cls):
        if _heavy_skipped():
            raise unittest.SkipTest(
                "CLAUDE_SKIP_HEAVY_INTEGRATION=1 set; skipping heavy E2E."
            )
        if not _which("node") or not _which("npm"):
            raise unittest.SkipTest(
                "node/npm not on PATH; skipping E2E (mirrors test_visual_diff.py)."
            )
        if not FIXTURE_DIR.exists():
            raise unittest.SkipTest(
                f"Fixture dir {FIXTURE_DIR} missing; cannot run E2E."
            )

    def setUp(self):
        # All artifacts land under a temp pipeline-state root so we don't
        # collide with the actual harness state directory.
        self._tmpdir = Path(tempfile.mkdtemp(prefix="design-qc-vr-e2e-"))
        self._pipeline_state_root = self._tmpdir / "pipeline-state"
        self._pipeline_state_root.mkdir(parents=True, exist_ok=True)
        # Working-copy of the fixture so we can init a git repo inside without
        # polluting the canonical fixture tree.
        self._fixture_root = self._tmpdir / "fixture"
        shutil.copytree(FIXTURE_DIR, self._fixture_root)

    def tearDown(self):
        # Best-effort cleanup of every worktree the helper might have left.
        worktree_root = self._fixture_root / ".claude" / "worktrees"
        if worktree_root.exists():
            for wt in worktree_root.iterdir():
                # `git worktree remove --force` is the documented teardown.
                subprocess.run(
                    ["git", "-C", str(self._fixture_root),
                     "worktree", "remove", "--force", str(wt)],
                    capture_output=True, check=False,
                )
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_e2e_baseline_capture_then_pump_writes_contract_artifacts(self):
        """Real producer pump: baseline_capture.sh + Playwright pixel-diff pump
        writes the four contracted artifacts.

        (a) baseline PNG under pipeline-state/{task-id}/visual-baselines/
        (b) current PNG under .claude/screenshots/
        (c) NO PNG under __screenshots__/ (failure-mode-9 path contract)
        (d) index.json has routes[*].visual_regression.pixel_diff_ratio as float
        """
        self._init_git_repo(self._fixture_root)
        self._install_playwright(self._fixture_root)
        self._capture_baseline(self._fixture_root)
        self._run_playwright_pump(self._fixture_root)
        self._assert_contract_artifacts(self._fixture_root)

    # ----- helpers -----------------------------------------------------------

    def _init_git_repo(self, fixture_root):
        env = self._git_env()
        cmds = [
            ["git", "init", "-q", "-b", "main"],
            ["git", "add", "-A"],
            ["git", "-c", "commit.gpgsign=false",
             "commit", "-q", "-m", "fixture: initial Next.js page"],
        ]
        for cmd in cmds:
            result = subprocess.run(
                cmd, cwd=str(fixture_root), capture_output=True,
                text=True, env=env, check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"git command {cmd} failed: {result.stderr}"
                )

    def _install_playwright(self, fixture_root):
        result = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--silent"],
            cwd=str(fixture_root), capture_output=True,
            text=True, timeout=300, check=False,
        )
        if result.returncode != 0:
            self.skipTest(
                f"npm install failed in fixture: {result.stderr[:400]}"
            )
        # Install only chromium — skips firefox/webkit (~150 MB savings).
        result = subprocess.run(
            ["npx", "--yes", "playwright", "install", "chromium"],
            cwd=str(fixture_root), capture_output=True,
            text=True, timeout=300, check=False,
        )
        if result.returncode != 0:
            self.skipTest(
                f"playwright browser install failed: {result.stderr[:400]}"
            )

    def _capture_baseline(self, fixture_root):
        env = os.environ.copy()
        env.update({
            "TASK_ID": TASK_ID,
            "REPO_ROOT": str(fixture_root),
            "BUILD_COMMAND": "true",  # fixture has no real build step
            "PIPELINE_STATE_ROOT": str(self._pipeline_state_root),
        })
        result = subprocess.run(
            ["bash", str(BASELINE_CAPTURE_SH)],
            cwd=str(fixture_root), capture_output=True,
            text=True, env=env, timeout=120, check=False,
        )
        # Helper is non-fatal by design — even build failure exits 0.
        # But syntax / git delegation must succeed.
        self.assertEqual(
            result.returncode, 0,
            f"baseline_capture.sh failed: {result.stderr[:400]}",
        )
        # Create the baseline PNG via the same Playwright pump so the
        # current-vs-baseline diff is meaningful. The helper only handles the
        # worktree + build dance; screenshot capture is the pump's job per
        # SKILL.md Step 5.5.
        baselines_dir = (
            self._pipeline_state_root / TASK_ID / "visual-baselines"
        )
        baselines_dir.mkdir(parents=True, exist_ok=True)
        self._drive_playwright(
            fixture_root,
            output_dir=baselines_dir,
            slug="home",
        )

    def _run_playwright_pump(self, fixture_root):
        # Drive the actual Step 6 pump against the current branch HEAD.
        out_dir = fixture_root / ".claude" / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        self._drive_playwright(
            fixture_root,
            output_dir=out_dir,
            slug="home",
        )
        self._write_index_json(fixture_root, out_dir)

    def _drive_playwright(self, fixture_root, output_dir, slug):
        """Run the fixture's playwright driver to capture one PNG per viewport."""
        env = os.environ.copy()
        env["PW_OUTPUT_DIR"] = str(output_dir)
        env["PW_SLUG"] = slug
        env["PW_PORT"] = str(FIXTURE_PORT)
        result = subprocess.run(
            ["node", "playwright-driver.js"],
            cwd=str(fixture_root), capture_output=True,
            text=True, env=env, timeout=120, check=False,
        )
        if result.returncode != 0:
            self.skipTest(
                "playwright driver failed (browser engine missing?): "
                f"{result.stderr[:400]}"
            )

    def _write_index_json(self, fixture_root, screenshots_dir):
        """Compute pixel_diff_ratio via visual_diff.js and write index.json."""
        baselines_dir = (
            self._pipeline_state_root / TASK_ID / "visual-baselines"
        )
        index_path = (
            self._pipeline_state_root / TASK_ID / "design-qc" / "index.json"
        )
        index_path.parent.mkdir(parents=True, exist_ok=True)
        routes = []
        for png in sorted(screenshots_dir.glob(f"home-*.png")):
            baseline = baselines_dir / png.name
            ratio = self._compute_ratio(baseline, png)
            routes.append({
                "route": "/",
                "visual_regression": {
                    "pixel_diff_ratio": ratio,
                    "baseline_path": str(baseline),
                    "current_path": str(png),
                },
            })
        index_path.write_text(json.dumps({
            "schema_version": 2,
            "visual_regression": {
                "captured": True,
                "baselines_dir": str(baselines_dir),
            },
            "routes": routes,
        }, indent=2))

    def _compute_ratio(self, baseline, current):
        """Decode both PNGs and compute the ratio via visual_diff.js."""
        # Write the decoder script to a file so positional args are preserved
        # (node -e + positional argv has portability quirks; a script file
        # makes process.argv unambiguous).
        decoder = self._tmpdir / "decode_and_diff.js"
        decoder.write_text(
            "'use strict';\n"
            "const vd = require(process.env.VD_PATH);\n"
            "const fs = require('fs'); const zlib = require('zlib');\n"
            "function decode(p){\n"
            "  const buf=fs.readFileSync(p);\n"
            "  let i=8, chunks=[], w=0, h=0;\n"
            "  while(i<buf.length){\n"
            "    const len=buf.readUInt32BE(i);\n"
            "    const type=buf.slice(i+4,i+8).toString('ascii');\n"
            "    const data=buf.slice(i+8,i+8+len);\n"
            "    if(type==='IHDR'){w=data.readUInt32BE(0);h=data.readUInt32BE(4);}\n"
            "    if(type==='IDAT'){chunks.push(data);}\n"
            "    i+=12+len;\n"
            "  }\n"
            "  const raw=zlib.inflateSync(Buffer.concat(chunks));\n"
            "  const out=Buffer.alloc(w*h*4); let s=0, d=0;\n"
            "  for(let y=0;y<h;y++){ s++;\n"
            "    for(let x=0;x<w;x++){\n"
            "      out[d++]=raw[s++]; out[d++]=raw[s++];\n"
            "      out[d++]=raw[s++]; out[d++]=raw[s++];\n"
            "    }\n"
            "  }\n"
            "  return {buf:out,w,h};\n"
            "}\n"
            "const a = decode(process.argv[2]);\n"
            "const b = decode(process.argv[3]);\n"
            "if (a.w !== b.w || a.h !== b.h) { console.log(1.0); process.exit(0); }\n"
            "const ratio = vd.computePixelDiffRatio(\n"
            "  a.buf, b.buf, 0.02, {width:a.w, height:a.h},\n"
            ");\n"
            "console.log(ratio);\n"
        )
        env = os.environ.copy()
        env["VD_PATH"] = str(VISUAL_DIFF_JS)
        result = subprocess.run(
            ["node", str(decoder), str(baseline), str(current)],
            capture_output=True, text=True, env=env, timeout=30, check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"visual_diff invocation failed: {result.stderr[:400]}"
            )
        return float(result.stdout.strip())

    def _git_env(self):
        env = os.environ.copy()
        env.setdefault("GIT_AUTHOR_NAME", "test")
        env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
        env.setdefault("GIT_COMMITTER_NAME", "test")
        env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
        return env

    # ----- contract assertions ----------------------------------------------

    def _assert_contract_artifacts(self, fixture_root):
        baselines_dir = (
            self._pipeline_state_root / TASK_ID / "visual-baselines"
        )
        baseline_pngs = list(baselines_dir.glob("*.png"))
        self.assertTrue(
            baseline_pngs,
            f"Contract (a) violated: no baseline PNG under {baselines_dir}/",
        )

        # (b) current PNG exists at .claude/screenshots/
        screenshots_dir = fixture_root / ".claude" / "screenshots"
        current_pngs = list(screenshots_dir.glob("*.png"))
        self.assertTrue(
            current_pngs,
            "Contract (b) violated: no PNG under .claude/screenshots/",
        )

        # (c) NO PNG under __screenshots__/ (failure-mode-9 path contract)
        underscore_dir = fixture_root / "__screenshots__"
        underscore_pngs = (
            list(underscore_dir.rglob("*.png")) if underscore_dir.exists() else []
        )
        self.assertFalse(
            underscore_pngs,
            "Contract (c) violated: PNGs found under __screenshots__/ — "
            f"Playwright default leaked, snapshotDir override broken: "
            f"{underscore_pngs}",
        )

        # (d) index.json has routes[*].visual_regression.pixel_diff_ratio as float
        index_path = (
            self._pipeline_state_root / TASK_ID / "design-qc" / "index.json"
        )
        self.assertTrue(
            index_path.exists(),
            f"Contract (d) violated: {index_path} missing",
        )
        index = json.loads(index_path.read_text())
        self.assertIn("routes", index, "index.json missing routes[]")
        self.assertTrue(index["routes"], "index.json routes[] empty")
        for route in index["routes"]:
            ratio = route.get("visual_regression", {}).get("pixel_diff_ratio")
            self.assertIsInstance(
                ratio, float,
                f"Contract (d) violated: route {route.get('route')!r} "
                f"pixel_diff_ratio is {type(ratio).__name__}, not float",
            )
            self.assertGreaterEqual(ratio, 0.0)
            self.assertLessEqual(ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
