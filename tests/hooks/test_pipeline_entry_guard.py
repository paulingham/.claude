"""Pipeline Entry Guard — unit + structural tests.

Tests the pure decision core in hooks/_lib/pipeline_entry_guard.py
and structural properties of the shell hook and hooks.json registration.

The conftest at tests/conftest.py prepends hooks/_lib to sys.path so
`from pipeline_entry_guard import decide` works directly.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from pipeline_entry_guard import decide
from pipeline_entry_guard_cli import (
    _write_bypass_ledger,
    _write_advisory_ledger,
    _intake_tier,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
HOOK_SH = HOOKS_DIR / "pipeline-entry-guard.sh"
HOOKS_JSON = HOOKS_DIR / "hooks.json"

_NO_SIGNALS = {
    "task_id": "",
    "has_active_pipeline": False,
    "intake_tier": "",
    "disabled": False,
}


def _ctx(**overrides):
    ctx = {**_NO_SIGNALS}
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# AC-1: Non-gated roles always allow
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", [
    "code-reviewer",
    "security-engineer",
    "architect",
    "fix-engineer",
    "product-reviewer",
    "patch-critic",
    "planning-agent",
])
def test_non_gated_roles_always_allow(role):
    result = decide(_ctx(role=role))
    assert result["action"] == "allow"


def test_empty_role_is_not_gated():
    result = decide(_ctx(role=""))
    assert result["action"] == "allow"


def test_non_gated_allow_even_with_disabled():
    result = decide(_ctx(role="code-reviewer", disabled=True))
    assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# AC-2: Gated roles block with no signals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", [
    "software-engineer",
    "frontend-engineer",
    "database-engineer",
    "infrastructure-engineer",
    "qa-engineer",
])
def test_gated_role_blocks_with_no_signals(role):
    result = decide(_ctx(role=role))
    assert result["action"] == "block"


def test_block_reason_mentions_role():
    result = decide(_ctx(role="software-engineer"))
    assert "software-engineer" in result["reason"]


# ---------------------------------------------------------------------------
# AC-3: task_id signal allows
# ---------------------------------------------------------------------------

def test_signal_task_id_allows():
    result = decide(_ctx(role="software-engineer", task_id="my-task"))
    assert result["action"] == "allow"
    assert result["signal"] == "task_id"


# ---------------------------------------------------------------------------
# AC-4: active_pipeline signal allows
# ---------------------------------------------------------------------------

def test_signal_active_pipeline_allows():
    result = decide(_ctx(role="software-engineer", task_id="", has_active_pipeline=True))
    assert result["action"] == "allow"
    assert result["signal"] == "active_pipeline"


# ---------------------------------------------------------------------------
# AC-5: intake_tier signal allows
# ---------------------------------------------------------------------------

def test_signal_intake_tier_allows():
    result = decide(_ctx(role="software-engineer", intake_tier="T5"))
    assert result["action"] == "allow"
    assert result["signal"] == "intake_tier"


@pytest.mark.parametrize("tier", ["T1", "T6"])
def test_signal_intake_tier_allows_any_tier(tier):
    result = decide(_ctx(role="software-engineer", intake_tier=tier))
    assert result["action"] == "allow"
    assert result["signal"] == "intake_tier"


# ---------------------------------------------------------------------------
# AC-6: disabled/bypass overrides everything
# ---------------------------------------------------------------------------

def test_bypass_overrides_block_no_signals():
    result = decide(_ctx(role="software-engineer", disabled=True))
    assert result["action"] == "bypass"


def test_bypass_overrides_even_with_all_signals():
    result = decide(_ctx(
        role="software-engineer",
        task_id="t",
        has_active_pipeline=True,
        intake_tier="T5",
        disabled=True,
    ))
    assert result["action"] == "bypass"


# ---------------------------------------------------------------------------
# AC-7: shell advisory properties
# ---------------------------------------------------------------------------

def test_shell_advisory_exit_is_exit_0_not_exit_2():
    content = HOOK_SH.read_text()
    assert "TODO(pipeline-entry-guard-promote)" in content
    assert "exit 0" in content
    assert "exit 2" not in content


# ---------------------------------------------------------------------------
# AC-8: hooks.json registration
# ---------------------------------------------------------------------------

def test_hooks_json_registers_pipeline_entry_guard_sh():
    data = json.loads(HOOKS_JSON.read_text())
    agent_blocks = [
        block for block in data["hooks"]["PreToolUse"]
        if block.get("matcher") == "Agent"
    ]
    assert len(agent_blocks) == 1, "Should be exactly one Agent matcher block"
    args_strs = [
        " ".join(h.get("args", []))
        for h in agent_blocks[0]["hooks"]
    ]
    assert any("pipeline-entry-guard.sh" in a for a in args_strs)


# ---------------------------------------------------------------------------
# AC-9: bash syntax valid
# ---------------------------------------------------------------------------

def test_shell_syntax_valid():
    result = subprocess.run(
        ["bash", "-n", str(HOOK_SH)],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()


# ---------------------------------------------------------------------------
# AC-10: signal precedence
# ---------------------------------------------------------------------------

def test_task_id_beats_active_pipeline():
    result = decide(_ctx(role="software-engineer", task_id="t", has_active_pipeline=True))
    assert result["signal"] == "task_id"


def test_task_id_beats_intake_tier():
    result = decide(_ctx(role="software-engineer", task_id="t", intake_tier="T5"))
    assert result["signal"] == "task_id"


def test_active_pipeline_beats_intake_tier():
    result = decide(_ctx(role="software-engineer", task_id="", has_active_pipeline=True, intake_tier="T5"))
    assert result["signal"] == "active_pipeline"


# ---------------------------------------------------------------------------
# AC-11: bypass ledger
# ---------------------------------------------------------------------------

def test_bypass_ledger_written(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-123")
    _write_bypass_ledger("software-engineer")
    ledger = tmp_path / "test-session-123" / "pipeline-entry-bypass.jsonl"
    assert ledger.exists()
    record = json.loads(ledger.read_text().strip())
    assert record["action"] == "bypass"
    assert record["env_var"] == "CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD"
    assert record["role"] == "software-engineer"
    assert "ts" in record
    assert "session_id" in record


# ---------------------------------------------------------------------------
# AC-12: advisory ledger
# ---------------------------------------------------------------------------

def test_advisory_ledger_written(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-456")
    _write_advisory_ledger("qa-engineer", "no pipeline signal")
    ledger = tmp_path / "test-session-456" / "pipeline-entry-advisory.jsonl"
    assert ledger.exists()
    record = json.loads(ledger.read_text().strip())
    assert record["action"] == "would_block"
    assert record["role"] == "qa-engineer"
    assert record["reason"] == "no pipeline signal"
    assert "ts" in record
    assert "session_id" in record


# ---------------------------------------------------------------------------
# AC-11/12: ledger write failure is fail-safe
# ---------------------------------------------------------------------------

def test_ledger_write_failure_is_fail_safe(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_METRICS_DIR", "/nonexistent-root-dir-xyz/no-write")
    # Must not raise — fail-safe
    _write_bypass_ledger("software-engineer")
    _write_advisory_ledger("software-engineer", "test reason")
    # stdout must stay empty (errors go to stderr only)
    captured = capsys.readouterr()
    assert captured.out == ""


# ---------------------------------------------------------------------------
# AC-13: _intake_tier reads real temp files (tier: and tier_emitted: forms)
# ---------------------------------------------------------------------------

def test_intake_tier_reads_tier_short_form(monkeypatch, tmp_path):
    state_dir = tmp_path / "pipeline-state"
    task_dir = state_dir / "my-task-id"
    task_dir.mkdir(parents=True)
    (task_dir / "intake.md").write_text('tier: "T4"\n')
    monkeypatch.setenv("HARNESS_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_WORKSTREAM", raising=False)
    assert _intake_tier("my-task-id") == "T4"


def test_intake_tier_reads_tier_emitted_form(monkeypatch, tmp_path):
    state_dir = tmp_path / "pipeline-state"
    task_dir = state_dir / "my-task-id"
    task_dir.mkdir(parents=True)
    (task_dir / "intake.md").write_text('tier_emitted: "T6"\n')
    monkeypatch.setenv("HARNESS_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_WORKSTREAM", raising=False)
    assert _intake_tier("my-task-id") == "T6"


def test_intake_tier_path_traversal_blocked(monkeypatch, tmp_path):
    """A task_id of ../../etc/passwd must not read outside state_dir."""
    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir(parents=True)
    monkeypatch.setenv("HARNESS_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_WORKSTREAM", raising=False)
    # Traversal attempt — must return "" not raise
    result = _intake_tier("../../etc/passwd")
    assert result == ""
