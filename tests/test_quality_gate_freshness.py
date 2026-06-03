"""Slice 4: hooks/_lib/quality-gate-checks.sh gains _qg_check_freshness;
hooks/quality-gate.sh adds `freshness` to its for-loop check list.

The check is a synchronous, blocking gate that runs on `gh pr create`.
- PASS (rc=0) when verification-evidence.json exists, has VERIFIED verdict,
  and git_head matches current HEAD.
- FAIL (rc=1) on any of: missing file, parse error, head mismatch, wrong verdict.

Style requirements (HIGH-SE2): use `jq` not `python3 -c` — matches the existing
_qg_* style (one-liner delegations to runtime CLIs).

Slice-1 additions: _qg_check_freshness receives $COMMAND (cd-prefix worktree
extraction), falls back to cwd HEAD when no cd-prefix, finds evidence by glob.
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


def _run_qg_freshness(cwd, command=None, env=None):
    """Source the lib + call _qg_check_freshness [command]; return CompletedProcess.

    command: if provided, passed as the first positional arg to _qg_check_freshness
             (the COMMAND string from quality-gate.sh, may contain a cd-prefix).
    """
    proc_env = {**os.environ, **(env or {})}
    if command is not None:
        # Shell-quote the command string so it's passed as a single argument.
        import shlex
        quoted_command = shlex.quote(command)
        cmd = f"source '{CHECKS_SH}' && _qg_check_freshness {quoted_command}"
    else:
        cmd = f"source '{CHECKS_SH}' && _qg_check_freshness"
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
            self.assertIn("[freshness] no verification-evidence", r.stderr)

    def test_qg_check_freshness_returns_1_when_head_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(repo, "test-task", git_head="deadbeef" * 5)
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task"})
            self.assertEqual(r.returncode, 1)
            # Operator Copy mandates BOTH heads echoed: state=X worktree=Y.
            self.assertIn(f"state={'deadbeef' * 5}", r.stderr)
            self.assertIn(f"worktree={head}", r.stderr)

    def test_qg_check_freshness_returns_1_when_verdict_not_verified(self):
        """Operator-error path: state file exists, head matches, but verdict
        is not VERIFIED. Distinct stderr message + verdict echoed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(repo, "test-task", git_head=head, verdict="UNVERIFIED")
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task"})
            self.assertEqual(r.returncode, 1)
            self.assertIn("verdict=UNVERIFIED", r.stderr)

    def test_qg_check_freshness_env_hatch_disables_processing(self):
        """CLAUDE_DISABLE_FRESHNESS_QG=1 short-circuits to rc=0 even with no
        state file (mirrors CLAUDE_DISABLE_FRESHNESS_GUARD on the Agent hook)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, _ = _make_repo_with_commit(Path(tmpdir))
            r = _run_qg_freshness(repo, env={"CLAUDE_PIPELINE_TASK_ID": "test-task",
                                              "CLAUDE_DISABLE_FRESHNESS_QG": "1"})
            self.assertEqual(r.returncode, 0,
                             f"env hatch must bypass freshness gate; stderr={r.stderr}")

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

    def test_quality_gate_sh_passes_command_not_rt_to_freshness_check(self):
        """AC5: quality-gate.sh must call _qg_check_freshness "$COMMAND" OUTSIDE the
        for-loop. freshness must NOT appear in `for check in ...` any longer."""
        text = GATE_SH.read_text()
        # freshness must NOT be in the for-loop anymore.
        import re
        self.assertNotRegex(
            text, r"for check in[^;]*\bfreshness\b",
            "freshness must be removed from the for-loop")
        # _qg_check_freshness must be called with $COMMAND (not $RT).
        self.assertRegex(
            text, r'_qg_check_freshness\s+"\$COMMAND"',
            'quality-gate.sh must call _qg_check_freshness "$COMMAND" outside the loop')

    # -------------------------------------------------------------------------
    # Slice-1 new tests (AC1-AC4, AC6, AC8, AC9)
    # -------------------------------------------------------------------------

    def test_freshness_passes_when_command_cd_prefix_worktree_head_matches_evidence(self):
        """AC1: PASS when COMMAND has cd-prefix, extracted worktree HEAD == evidence.git_head
        and verdict is VERIFIED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(worktree, "test-task", git_head=head)
            # Simulate: cd "<worktree>" && gh pr create ...
            command = f'cd "{worktree}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            r = _run_qg_freshness(Path(tmpdir), command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"AC1: expected PASS for cd-prefix matching worktree HEAD; stderr={r.stderr}")

    def test_freshness_fails_when_command_cd_prefix_worktree_head_stale(self):
        """AC2: FAIL when COMMAND cd-prefix worktree HEAD != evidence.git_head."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree, head = _make_repo_with_commit(Path(tmpdir))
            stale_sha = "deadbeef" * 5
            _write_evidence(worktree, "test-task", git_head=stale_sha)
            command = f'cd "{worktree}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            r = _run_qg_freshness(Path(tmpdir), command=command, env=env)
            self.assertEqual(r.returncode, 1,
                             f"AC2: expected FAIL for stale evidence; stderr={r.stderr}")
            self.assertIn(f"state={stale_sha}", r.stderr,
                          "AC2: stderr must include state=<stale SHA>")
            self.assertIn(f"worktree={head}", r.stderr,
                          "AC2: stderr must include worktree=<current HEAD>")

    def test_freshness_passes_cwd_fallback_when_no_cd_prefix(self):
        """AC3: PASS when COMMAND has no cd-prefix; falls back to cwd HEAD (NOT fail-closed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(repo, "test-task", git_head=head)
            # COMMAND without cd-prefix — bare gh pr create
            command = "gh pr create --title test"
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            r = _run_qg_freshness(repo, command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"AC3: expected PASS for cwd-fallback; stderr={r.stderr}")

    def test_freshness_passes_when_repo_root_differs_but_worktree_matches(self):
        """AC4: PASS when REPO_ROOT (main) HEAD differs from worktree HEAD, but
        cd-prefix worktree HEAD == evidence.git_head — the correct HEAD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Create 'main' repo (hook cwd, REPO_ROOT analog)
            main_repo, _main_head = _make_repo_with_commit(tmp)
            # Create separate 'worktree' repo (PR branch)
            worktree, wt_head = _make_repo_with_commit(tmp)
            # Evidence lives in the worktree and matches worktree HEAD.
            _write_evidence(worktree, "test-task", git_head=wt_head)
            command = f'cd "{worktree}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            # Run from main_repo cwd (different HEAD)
            r = _run_qg_freshness(main_repo, command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"AC4: expected PASS when worktree matches evidence; stderr={r.stderr}")

    def test_freshness_passes_quoted_path_with_spaces_in_command(self):
        """AC6: PASS when COMMAND has a quoted cd path containing spaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Create a directory with spaces
            spaced = tmp / "my work tree"
            spaced.mkdir()
            # init a real git repo there
            env_git = {**os.environ,
                       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            subprocess.run(["git", "init", "-q", "-b", "main", str(spaced)],
                           check=True, env=env_git)
            (spaced / "README").write_text("init\n")
            subprocess.run(["git", "-C", str(spaced), "add", "README"],
                           check=True, env=env_git)
            subprocess.run(["git", "-C", str(spaced), "commit", "-q", "-m", "init"],
                           check=True, env=env_git)
            head = subprocess.run(
                ["git", "-C", str(spaced), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, env=env_git).stdout.strip()
            _write_evidence(spaced, "test-task", git_head=head)
            # Quoted path with space
            command = f'cd "{spaced}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            r = _run_qg_freshness(spaced, command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"AC6: expected PASS for quoted path with spaces; stderr={r.stderr}")

    def test_freshness_passes_when_task_id_unset_evidence_found_by_glob(self):
        """AC8: PASS when CLAUDE_PIPELINE_TASK_ID is unset; evidence found by
        globbing <worktree>/pipeline-state/*/verification-evidence.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree, head = _make_repo_with_commit(Path(tmpdir))
            # Write evidence under some task dir (not named 'unknown')
            _write_evidence(worktree, "some-task-id", git_head=head)
            command = f'cd "{worktree}" && gh pr create --title "test"'
            # Explicitly unset CLAUDE_PIPELINE_TASK_ID
            env = {k: v for k, v in os.environ.items()
                   if k != "CLAUDE_PIPELINE_TASK_ID"}
            r = _run_qg_freshness(Path(tmpdir), command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"AC8: expected PASS with task-id unset, glob finds evidence; stderr={r.stderr}")

    def test_freshness_task_id_hint_prefers_correct_evidence_over_newest_glob(self):
        """Mutation guard (d): when CLAUDE_PIPELINE_TASK_ID is set and the task-specific
        evidence file exists, it must be preferred over the most-recently-modified file
        found by glob (which may belong to a different task and have a stale HEAD)."""
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree, head = _make_repo_with_commit(Path(tmpdir))
            # Write evidence for the correct task (matching HEAD).
            _write_evidence(worktree, "correct-task", git_head=head)
            time.sleep(0.05)
            # Write evidence for a different task (stale HEAD) — newer mtime.
            _write_evidence(worktree, "other-task", git_head="deadbeef" * 5)
            command = f'cd "{worktree}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "correct-task"}
            r = _run_qg_freshness(Path(tmpdir), command=command, env=env)
            self.assertEqual(r.returncode, 0,
                             f"task-id hint must prefer correct-task over newer other-task; stderr={r.stderr}")

    def test_freshness_fails_when_verdict_not_verified_after_refactor(self):
        """AC9: FAIL when evidence present, git_head matches, verdict != VERIFIED.
        Stderr must contain verdict=<V>; re-verify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree, head = _make_repo_with_commit(Path(tmpdir))
            _write_evidence(worktree, "test-task", git_head=head, verdict="PARTIAL")
            command = f'cd "{worktree}" && gh pr create --title "test"'
            env = {"CLAUDE_PIPELINE_TASK_ID": "test-task"}
            r = _run_qg_freshness(Path(tmpdir), command=command, env=env)
            self.assertEqual(r.returncode, 1,
                             f"AC9: expected FAIL for non-VERIFIED verdict; stderr={r.stderr}")
            self.assertIn("verdict=PARTIAL", r.stderr,
                          "AC9: stderr must include verdict=PARTIAL")
            self.assertIn("re-verify", r.stderr,
                          "AC9: stderr must include re-verify")


if __name__ == "__main__":
    unittest.main()
