"""Slice 3: verification-freshness-guard.sh — Path-B advisory hook.

The hook is a PreToolUse Agent hook that compares the recorded `git_head` in
`pipeline-state/{task-id}/verification-evidence.json` to the current worktree
HEAD and emits a JSONL record to `metrics/{session}/freshness-guard.jsonl`.

At v2.1.141 it is log-only (exit 0 always). Promotion to exit-2 is a single-file
flip once `permissionDecision` ships on the Agent matcher.

Tests cover:
  - Path-B template shape (existence, header annotations)
  - Gating (only patch-critic / product-reviewer / pr-creation; only Agent tool)
  - HEAD resolution rules (env → cwd → skip-clean)
  - All 9 reason enum values: fresh, state_file_missing, git_head_mismatch,
    hard_staleness, no_worktree_resolvable, sandbox_staleness,
    state_file_parse_error, git_timeout, invalid_task_id
  - env-hatch + hook-profile suppression
  - Path-traversal safety on CLAUDE_SESSION_ID
  - Headline scenario: fix-engineer re-dispatch invalidates git_head
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "verification-freshness-guard.sh"

GATED = "patch-critic"


_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)
_REPO_ROOT = REPO_ROOT


def _run_hook(payload, env=None, plugin_data=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env = {**os.environ, "PYTHONPATH": merged_pp,
                "CLAUDE_PLUGIN_ROOT": str(_REPO_ROOT)}
    # Always inject CLAUDE_PLUGIN_DATA so writes go to a hermetic dir.
    # Do NOT override HOME — freshness hook runs git commands which need
    # a valid HOME for gitconfig.
    effective_pd = plugin_data if plugin_data is not None else _GLOBAL_PLUGIN_DATA
    proc_env["CLAUDE_PLUGIN_DATA"] = str(effective_pd)
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=15, env=proc_env)


_GLOBAL_PLUGIN_DATA = Path(tempfile.mkdtemp(prefix="freshness-global-"))


def _log_path(session, filename="freshness-guard.jsonl", base=None):
    root = base if base is not None else _GLOBAL_PLUGIN_DATA
    return root / "metrics" / session / filename


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


def _make_repo_with_commit(tmp_path, message="initial"):
    """Make a temp git repo so worktree HEAD is resolvable + controllable."""
    repo = tmp_path / f"repo-{uuid.uuid4().hex[:8]}"
    repo.mkdir()
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                   check=True, env=env)
    (repo / "README").write_text(message + "\n")
    subprocess.run(["git", "-C", str(repo), "add", "README"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message],
                   check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, env=env).stdout.strip()
    return repo, head


def _make_evidence_dir(repo, task_id):
    """Create pipeline-state/{task}/ inside the worktree."""
    evidence_dir = repo / "pipeline-state" / task_id
    evidence_dir.mkdir(parents=True)
    return evidence_dir


def _write_evidence(evidence_dir, *, git_head, generated_at="2026-05-14T12:00:00Z",
                    verdict="VERIFIED", sandbox_status="SANDBOX_VERIFIED"):
    """Write a verification-evidence.json file with the given fields."""
    payload = {
        "schema_version": 1,
        "task_id": "test-task",
        "git_head": git_head,
        "generated_at": generated_at,
        "verdict": verdict,
        "tier_results": {
            "contract": {"status": "PASS"},
            "smoke": {"status": "PASS"},
            "mutation": {"status": "PASS", "score": 0.78},
        },
        "sandbox_run": {"status": sandbox_status, "session": "e2b-test"},
    }
    (evidence_dir / "verification-evidence.json").write_text(json.dumps(payload))


class HookFileExistsAndShape(unittest.TestCase):
    def test_hook_file_exists_and_executable(self):
        self.assertTrue(HOOK.exists(), f"expected hook at {HOOK}")
        self.assertTrue(os.access(HOOK, os.X_OK),
                        f"hook must be executable: {HOOK}")

    def test_hook_header_declares_enforces_and_protects(self):
        text = HOOK.read_text()
        # Forensics §Step 3b joins violations back to # enforces: / # protects: annotations.
        self.assertRegex(text, r"# enforces:\s*rules/core\.md")
        self.assertRegex(text, r"# protects:\s*verify")


class HookGatingByRoleAndTool(unittest.TestCase):
    def test_hook_skips_silently_on_non_gated_role(self):
        session = f"test-ng-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(_log_path(session).exists(),
                             "non-gated role should not write freshness JSONL")
        finally:
            _cleanup(_log_path(session))

    def test_hook_skips_silently_on_non_agent_tool(self):
        session = f"test-nat-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Bash", "tool_input": {}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(_log_path(session).exists(),
                             "non-Agent tool should not write freshness JSONL")
        finally:
            _cleanup(_log_path(session))

    def test_gated_roles_set_is_hardcoded_no_env_override(self):
        """MEDIUM-PR3: CLAUDE_FRESHNESS_GATED_ROLES has no effect; the set is
        hard-coded inside the resolver."""
        session = f"test-hc-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_FRESHNESS_GATED_ROLES": "software-engineer"})
            self.assertEqual(result.returncode, 0)
            # software-engineer is NOT gated; env var must not change that.
            self.assertFalse(_log_path(session).exists())
        finally:
            _cleanup(_log_path(session))


class HookHeadResolution(unittest.TestCase):
    def test_hook_skips_cleanly_when_no_worktree_resolvable(self):
        """Rule 3: neither $CLAUDE_WORKTREE_PATH nor cwd resolves → skip-clean."""
        session = f"test-nw-{uuid.uuid4()}"
        try:
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_WORKTREE_PATH": "/nonexistent-path-xyz",
                     "CLAUDE_PIPELINE_TASK_ID": "test-task"})
            log = _log_path(session)
            self.assertTrue(log.exists(), "skip-clean still emits a JSONL line")
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "fresh")
            self.assertEqual(entry["resolved"]["reason"], "no_worktree_resolvable")
        finally:
            _cleanup(_log_path(session))


class HookEnumReasons(unittest.TestCase):
    """One test per reason value in the 8-enum vocabulary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.plugin_data = Path(tempfile.mkdtemp(prefix="freshness-test-"))

    def tearDown(self):
        self.tmp.cleanup()
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _spawn(self, *, worktree, env_overrides=None):
        session = f"test-{uuid.uuid4()}"
        env = {"CLAUDE_SESSION_ID": session,
               "CLAUDE_WORKTREE_PATH": str(worktree),
               "CLAUDE_PIPELINE_TASK_ID": "test-task"}
        if env_overrides:
            env.update(env_overrides)
        _run_hook(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": GATED}},
            env=env, plugin_data=self.plugin_data)
        return session, _log_path(session, base=self.plugin_data)

    def test_state_file_missing_yields_would_block(self):
        repo, _ = _make_repo_with_commit(self.tmp_path)
        # Do NOT create the evidence file.
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"], "state_file_missing")
        finally:
            _cleanup(log)

    def test_git_head_mismatch_yields_would_block_hard(self):
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        _write_evidence(evidence_dir, git_head="deadbeef" * 5)  # not real HEAD
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"], "git_head_mismatch")
            self.assertEqual(entry["resolved"]["staleness_class"], "hard")
        finally:
            _cleanup(log)

    def test_fresh_state_yields_fresh_action(self):
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        _write_evidence(evidence_dir, git_head=head)
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "fresh")
            self.assertEqual(entry["resolved"]["reason"], "fresh")
        finally:
            _cleanup(log)

    def test_hard_staleness_yields_would_block(self):
        """generated_at > HARD_TTL_SEC ago → would_block/hard_staleness."""
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        # 2 years ago — definitely > 24h default.
        _write_evidence(evidence_dir, git_head=head,
                        generated_at="2024-01-01T00:00:00Z")
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"], "hard_staleness")
            self.assertEqual(entry["resolved"]["staleness_class"], "hard")
        finally:
            _cleanup(log)

    def test_sandbox_staleness_yields_would_block(self):
        """LOW-PR1: sandbox check runs BEFORE git_head check; first-failure wins."""
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        # Set sandbox status to non-VERIFIED but git_head is correct — sandbox check
        # must fire first, surfacing sandbox_staleness (not git_head_mismatch).
        _write_evidence(evidence_dir, git_head=head,
                        sandbox_status="SANDBOX_SKIPPED")
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"], "sandbox_staleness")
        finally:
            _cleanup(log)

    def test_state_file_parse_error_yields_would_block(self):
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        (evidence_dir / "verification-evidence.json").write_text("not json {{{")
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"],
                             "state_file_parse_error")
        finally:
            _cleanup(log)

    def test_verdict_not_verified_yields_would_block(self):
        """final-gate round 1 product-acceptance REJECT-1: state file with
        verdict != VERIFIED is an operator-error path distinct from staleness.
        Symmetry between synchronous gate (_qg_check_freshness) and the
        async resolver — both surface `verdict_not_verified`."""
        repo, head = _make_repo_with_commit(self.tmp_path)
        evidence_dir = _make_evidence_dir(repo, "test-task")
        _write_evidence(evidence_dir, git_head=head, verdict="UNVERIFIED")
        session, log = self._spawn(worktree=repo)
        try:
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "would_block")
            self.assertEqual(entry["resolved"]["reason"],
                             "verdict_not_verified")
            self.assertEqual(entry["resolved"].get("verdict"), "UNVERIFIED")
        finally:
            _cleanup(log)


class HookEscapeHatchAndProfile(unittest.TestCase):
    def test_env_hatch_disables_processing(self):
        session = f"test-eh-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_FRESHNESS_GUARD": "1"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(_log_path(session).exists())
        finally:
            _cleanup(_log_path(session))

    def test_minimal_profile_suppresses_hook(self):
        session = f"test-mp-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_HOOK_PROFILE": "minimal"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(_log_path(session).exists())
        finally:
            _cleanup(_log_path(session))


class HookPathTraversalSafety(unittest.TestCase):
    def test_traversal_session_id_does_not_escape_metrics_dir(self):
        target = Path("/tmp/sec-poc-freshness/PWNED")
        if target.exists():
            target.unlink()
        if target.parent.exists():
            try:
                target.parent.rmdir()
            except OSError:
                pass
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED}},
                env={"CLAUDE_SESSION_ID": "../../../../tmp/sec-poc-freshness/PWNED"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(target.exists(),
                             "traversal escaped sandbox; sanitisation broken")
        finally:
            if target.exists():
                target.unlink()
            if target.parent.exists():
                try:
                    target.parent.rmdir()
                except OSError:
                    pass


class HookHeadlineFixEngineerRedispatch(unittest.TestCase):
    """AC3.15 / MEDIUM-PR4: the canonical scenario the proposal closes.

    Sequence:
      1. /verify writes verification-evidence.json with git_head = HEAD_A
      2. fix-engineer Edit advances HEAD to HEAD_B
      3. orchestrator dispatches patch-critic
      → hook MUST emit would_block / git_head_mismatch / hard.
    """

    def test_freshness_guard_catches_fix_engineer_redispatch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head_a = _make_repo_with_commit(Path(tmpdir),
                                                  message="initial-A")
            evidence_dir = _make_evidence_dir(repo, "test-task")
            _write_evidence(evidence_dir, git_head=head_a)

            # Simulate fix-engineer re-dispatch — new commit, HEAD advances.
            env = {**os.environ,
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            (repo / "README").write_text("fix-engineer-edit-B\n")
            subprocess.run(["git", "-C", str(repo), "add", "README"],
                           check=True, env=env)
            subprocess.run(["git", "-C", str(repo), "commit", "-q",
                            "-m", "fix-engineer fix"],
                           check=True, env=env)
            head_b = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
                env=env).stdout.strip()
            self.assertNotEqual(head_a, head_b)

            # Now spawn patch-critic.
            session = f"test-redispatch-{uuid.uuid4()}"
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": GATED}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_WORKTREE_PATH": str(repo),
                         "CLAUDE_PIPELINE_TASK_ID": "test-task"})
                log = _log_path(session)
                entry = json.loads(log.read_text().strip().splitlines()[-1])
                self.assertEqual(entry["resolved"]["action"], "would_block")
                self.assertEqual(entry["resolved"]["reason"],
                                 "git_head_mismatch")
                self.assertEqual(entry["resolved"]["staleness_class"], "hard")
                self.assertEqual(entry["resolved"]["state_file_head"], head_a)
                self.assertEqual(entry["resolved"]["worktree_head"], head_b)
            finally:
                _cleanup(_log_path(session))


class HookEmitsAdvisorySourceToken(unittest.TestCase):
    """All Path-B advisory hooks tag source: path-b-advisory in the JSONL."""

    def test_source_field_is_path_b_advisory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            evidence_dir = _make_evidence_dir(repo, "test-task")
            _write_evidence(evidence_dir, git_head=head)
            session = f"test-src-{uuid.uuid4()}"
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": GATED}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_WORKTREE_PATH": str(repo),
                         "CLAUDE_PIPELINE_TASK_ID": "test-task"})
                log = _log_path(session)
                entry = json.loads(log.read_text().strip().splitlines()[-1])
                self.assertEqual(entry["source"], "path-b-advisory")
                self.assertEqual(entry["agent_role"], GATED)
            finally:
                _cleanup(_log_path(session))


class HookHeadResolutionPrecedence(unittest.TestCase):
    """Adversarial: env beats cwd. Without this test, a swap of the rule order
    would survive — only the env path is set in most other tests."""

    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="freshness-prec-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def test_env_takes_precedence_over_cwd_when_both_resolve(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            repo_a, head_a = _make_repo_with_commit(Path(a), "A")
            repo_b, _head_b = _make_repo_with_commit(Path(b), "B")
            evidence_dir = _make_evidence_dir(repo_a, "test-task")
            _write_evidence(evidence_dir, git_head=head_a)
            session = f"test-prec-{uuid.uuid4()}"
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED,
                                "cwd": str(repo_b)}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_WORKTREE_PATH": str(repo_a),
                     "CLAUDE_PIPELINE_TASK_ID": "test-task"},
                plugin_data=self.plugin_data)
            log = _log_path(session, base=self.plugin_data)
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "fresh")
            self.assertEqual(entry["resolved"]["worktree_head"], head_a)


class HookTtlBoundary(unittest.TestCase):
    """Adversarial: TTL comparison `>` not `>=`. With short TTL, exactly-on-
    boundary should NOT trigger hard_staleness; a couple seconds past should."""

    def test_ttl_threshold_is_strict_greater_than(self):
        """An evidence file 2s old should not be hard-stale with TTL=3600."""
        import tempfile
        from datetime import datetime, timezone, timedelta
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            evidence_dir = _make_evidence_dir(repo, "test-task")
            ts = (datetime.now(timezone.utc) - timedelta(seconds=2)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            _write_evidence(evidence_dir, git_head=head, generated_at=ts)
            session = f"test-ttl-{uuid.uuid4()}"
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": GATED}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_WORKTREE_PATH": str(repo),
                         "CLAUDE_PIPELINE_TASK_ID": "test-task",
                         "CLAUDE_FRESHNESS_HARD_TTL_SEC": "3600"})
                log = _log_path(session)
                entry = json.loads(log.read_text().strip().splitlines()[-1])
                self.assertEqual(entry["resolved"]["action"], "fresh")
            finally:
                _cleanup(_log_path(session))


class HookInvalidTtlEnvSecurity(unittest.TestCase):
    """LOW-SEC1: a non-integer CLAUDE_FRESHNESS_HARD_TTL_SEC must not crash the
    resolver at import time. The bash wrapper exits 0 either way, but a crash
    silently loses the would_block signal — the resolver must fall back to the
    default TTL and emit a normal verdict."""

    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="freshness-ttl-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def test_invalid_ttl_env_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, head = _make_repo_with_commit(Path(tmpdir))
            evidence_dir = _make_evidence_dir(repo, "test-task")
            _write_evidence(evidence_dir, git_head=head)
            session = f"test-bad-ttl-{uuid.uuid4()}"
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": GATED}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_WORKTREE_PATH": str(repo),
                     "CLAUDE_PIPELINE_TASK_ID": "test-task",
                     "CLAUDE_FRESHNESS_HARD_TTL_SEC": "abc-not-an-int"},
                plugin_data=self.plugin_data)
            self.assertEqual(result.returncode, 0)
            log = _log_path(session, base=self.plugin_data)
            self.assertTrue(log.exists(),
                            "resolver must still emit a JSONL line; "
                            "crash on bad TTL silently loses signal")
            entry = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["resolved"]["action"], "fresh")
            self.assertEqual(entry["resolved"]["reason"], "fresh")


class HookTaskIdTraversalHardening(unittest.TestCase):
    """LOW-SEC2: CLAUDE_PIPELINE_TASK_ID must be validated against
    ``^[a-z0-9_-]+$`` before being interpolated into the evidence file path.
    Adversarial task_id values (`../../etc/passwd`, slashes, dots) must yield
    `would_block / invalid_task_id` and must not cause a read outside
    `pipeline-state/`."""

    def test_invalid_task_id_yields_invalid_task_id_reason(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, _head = _make_repo_with_commit(Path(tmpdir))
            session = f"test-bad-tid-{uuid.uuid4()}"
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": GATED}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_WORKTREE_PATH": str(repo),
                         "CLAUDE_PIPELINE_TASK_ID": "../../etc/passwd"})
                log = _log_path(session)
                self.assertTrue(log.exists())
                entry = json.loads(log.read_text().strip().splitlines()[-1])
                self.assertEqual(entry["resolved"]["action"], "would_block")
                self.assertEqual(entry["resolved"]["reason"], "invalid_task_id")
            finally:
                _cleanup(_log_path(session))

    def test_invalid_task_id_does_not_read_outside_pipeline_state(self):
        """Plant a sentinel file at a traversal target; the resolver must NOT
        open it. The sentinel sits OUTSIDE the worktree's pipeline-state dir;
        if validation is correct, its contents must not appear in the JSONL."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            repo, _head = _make_repo_with_commit(Path(tmpdir))
            sentinel_dir = Path(tmpdir) / "sentinel"
            sentinel_dir.mkdir()
            sentinel = sentinel_dir / "verification-evidence.json"
            sentinel.write_text('{"git_head":"ATTACKER","sandbox_run":'
                                '{"status":"SANDBOX_VERIFIED"}}')
            # Traversal task_id pointing at the sentinel from inside repo's
            # pipeline-state/ would be `../../sentinel`.
            traversal = "../../sentinel"
            session = f"test-trav-{uuid.uuid4()}"
            try:
                _run_hook(
                    {"tool_name": "Agent",
                     "tool_input": {"subagent_type": GATED}},
                    env={"CLAUDE_SESSION_ID": session,
                         "CLAUDE_WORKTREE_PATH": str(repo),
                         "CLAUDE_PIPELINE_TASK_ID": traversal})
                log = _log_path(session)
                entry = json.loads(log.read_text().strip().splitlines()[-1])
                # Verdict must be invalid_task_id — NOT git_head_mismatch
                # (which is what would happen if the resolver read the sentinel
                # and saw a different git_head).
                self.assertEqual(entry["resolved"]["reason"],
                                 "invalid_task_id")
                self.assertNotIn("ATTACKER", json.dumps(entry),
                                 "sentinel contents leaked into JSONL — "
                                 "resolver read outside pipeline-state/")
            finally:
                _cleanup(_log_path(session))


if __name__ == "__main__":
    unittest.main()
