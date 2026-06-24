"""B7/B8 — deploy-outcome-emit.py unit tests.

B7: build_record composes valid deploy_outcome dict with required keys.
B8: append uses O_NOFOLLOW + O_APPEND, refuses symlinked target.
"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMIT_MODULE = REPO_ROOT / "hooks" / "_lib" / "deploy-outcome-emit.py"


def _load_emit():
    spec = importlib.util.spec_from_file_location("deploy_outcome_emit", EMIT_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_record_has_required_keys() -> None:
    mod = _load_emit()
    record = mod.build_record(
        pipeline_id="task-123",
        outcome="DEPLOYED",
        environment="staging",
        timestamp="2026-01-01T00:00:00Z",
    )
    assert record["record_type"] == "deploy_outcome"
    assert record["pipeline_id"] == "task-123"
    assert record["outcome"] == "DEPLOYED"
    assert record["environment"] == "staging"
    assert record["timestamp"] == "2026-01-01T00:00:00Z"


def test_build_record_outcome_enum_valid() -> None:
    mod = _load_emit()
    for outcome in ("DEPLOYED", "DEPLOY_FAILED", "ROLLED_BACK", "AUTO_ROLLBACK"):
        record = mod.build_record("p", outcome, "prod", "2026-01-01T00:00:00Z")
        assert record["outcome"] == outcome


def test_build_record_unknown_outcome_sentinel() -> None:
    mod = _load_emit()
    record = mod.build_record("p", "NOT_VALID", "prod", "2026-01-01T00:00:00Z")
    assert record["outcome"] == "<unknown>"


def test_append_jsonl_writes_record() -> None:
    mod = _load_emit()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "observations.jsonl")
        record = {"record_type": "deploy_outcome", "outcome": "DEPLOYED"}
        mod.append_jsonl(path, record)
        data = json.loads(Path(path).read_text().strip())
        assert data["outcome"] == "DEPLOYED"


def test_append_jsonl_refuses_symlinked_target() -> None:
    mod = _load_emit()
    with tempfile.TemporaryDirectory() as tmpdir:
        real = os.path.join(tmpdir, "real.jsonl")
        symlink = os.path.join(tmpdir, "sym.jsonl")
        Path(real).write_text("")
        os.symlink(real, symlink)
        # append_jsonl must raise OSError (ENOFOLLOW / ELOOP) on symlink
        raised = False
        try:
            mod.append_jsonl(symlink, {"test": True})
        except OSError:
            raised = True
        assert raised, "append_jsonl should refuse a symlinked target via O_NOFOLLOW"


def test_main_returns_0_on_wrong_argc() -> None:
    mod = _load_emit()
    result = mod.main(["script"])  # too few args
    assert result == 0


def test_main_returns_0_on_correct_args() -> None:
    mod = _load_emit()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = mod.main([
            "script",
            tmpdir,
            "2026-01-01T00:00:00Z",
            "pipe-1",
            "DEPLOYED",
            "staging",
        ])
        assert result == 0
        obs = os.path.join(tmpdir, "observations.jsonl")
        assert os.path.exists(obs)
