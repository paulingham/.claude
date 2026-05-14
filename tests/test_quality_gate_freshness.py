"""Slice 4: hooks/_lib/quality-gate-checks.sh gains _qg_check_freshness;
hooks/quality-gate.sh adds `freshness` to its for-loop check list.

The check is a synchronous, blocking gate that runs on `gh pr create`.
- PASS (rc=0) when verification-evidence.json exists, has VERIFIED verdict,
  and git_head matches current HEAD.
- FAIL (rc=1) on any of: missing file, parse error, head mismatch, wrong verdict.

Style requirements (HIGH-SE2): use `jq` not `python3 -c` — matches the existing
_qg_* style (one-liner delegations to runtime CLIs).
"""
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKS_SH = REPO_ROOT / "hooks" / "_lib" / "quality-gate-checks.sh"
GATE_SH = REPO_ROOT / "hooks" / "quality-gate.sh"


def _run_qg_freshness(cwd, env=None):
    """Source the lib + call _qg_check_freshness; return rc."""
    proc_env = {**os.environ, **(env or {})}
    cmd = (f"source '{CHECKS_SH}' && _qg_check_freshness")
    return subprocess.run(
        ["bash", "-c", cmd], cwd=str(cwd),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _make_repo_with_commit(tmp_path):
    repo = tmp_path / f"repo-{uuid.uuid4().hex[:8]}"
    repo.mkdir()
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                   check=True, env=env)
    (repo / "README").write_text("init\n")
    subprocess.run(["git", "-C", str(repo), "add", "README"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"],
                   check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, env=env).stdout.strip()
    return repo, head


def _write_evidence(repo, task, *, git_head, verdict="VERIFIED"):
    import json
    d = repo / "pipeline-state" / task
    d.mkdir(parents=True)
    (d / "verification-evidence.json").write_text(json.dumps({
        "schema_version": 1, "task_id": task, "git_head": git_head,
        "generated_at": "2026-05-14T12:00:00Z", "verdict": verdict,
        "tier_results": {}, "sandbox_run": {"status": "SANDBOX_VERIFIED"}}))


class QgFreshnessCheck(unittest.TestCase):
    def test_qg_check_freshness_returns_0_when_evidence_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(repo, "test-task", git_head=head)
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task"})
            self.assertEqual(r.returncode, 0,
                             f"expected PASS for fresh evidence; stderr={r.stderr}")

    def test_qg_check_freshness_returns_1_when_state_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, _ = _make_repo_with_commit(Path(tmpdir))
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task"})
            self.assertEqual(r.returncode, 1)

    def test_qg_check_freshness_returns_1_when_head_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, _ = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(repo, "test-task", git_head="deadbeef" * 5)
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task"})
            self.assertEqual(r.returncode, 1)

    def test_qg_check_freshness_uses_jq_not_python3(self):
        """HIGH-SE2: matches existing _qg_* style (jq delegations, no python3 -c)."""
        text = CHECKS_SH.read_text()
        # Find the function body.
        idx = text.find("_qg_check_freshness()")
        self.assertGreater(idx, 0, "function must be defined")
        # Body ends at the next top-level '_qg_' definition or EOF.
        rest = text[idx:]
        body_end = rest.find("\n_qg_", 50)
        body = rest[:body_end] if body_end > 0 else rest
        self.assertIn("jq", body, "must use jq for JSON parse")
        self.assertNotIn("python3 -c", body,
                         "MUST NOT use python3 -c — _qg_* style is jq-only")

    def test_quality_gate_sh_iterates_freshness_in_check_loop(self):
        """AC4.5: the for-loop must include `freshness`."""
        text = GATE_SH.read_text()
        # Match `for check in tests lint audit shape contract freshness;`
        # (order may vary but freshness MUST appear in the same loop).
        self.assertRegex(text,
                         r"for check in[^;]*\bfreshness\b",
                         "quality-gate.sh must add `freshness` to the for-loop")


if __name__ == "__main__":
    unittest.main()
