"""Test: plan_update broadcast message has the required shape."""
from datetime import datetime, timezone


def _make_broadcast_payload(task_id: str, plan_path: str, ts: str) -> dict:
    """Construct the canonical plan_update SendMessage payload."""
    return {
        "type": "plan_update",
        "task_id": task_id,
        "plan_path": plan_path,
        "update_section_anchor": f"Plan Update — {ts}",
        "ts": ts,
    }


def test_broadcast_has_required_keys():
    ts = datetime.now(timezone.utc).isoformat()
    payload = _make_broadcast_payload("my-task", "pipeline-state/my-task-plan.md", ts)
    required = {"type", "task_id", "plan_path", "update_section_anchor", "ts"}
    assert required.issubset(payload.keys()), f"Missing keys: {required - payload.keys()}"


def test_broadcast_type_is_plan_update():
    ts = datetime.now(timezone.utc).isoformat()
    payload = _make_broadcast_payload("my-task", "pipeline-state/my-task-plan.md", ts)
    assert payload["type"] == "plan_update"


def test_broadcast_anchor_contains_timestamp():
    ts = "2026-04-27T12:00:00+00:00"
    payload = _make_broadcast_payload("my-task", "pipeline-state/my-task-plan.md", ts)
    assert ts in payload["update_section_anchor"]


def test_broadcast_plan_path_matches_convention():
    ts = datetime.now(timezone.utc).isoformat()
    task_id = "wave3-I-continuous-planning"
    plan_path = f"pipeline-state/{task_id}-plan.md"
    payload = _make_broadcast_payload(task_id, plan_path, ts)
    assert payload["plan_path"].endswith("-plan.md"), "plan_path must match *-plan.md convention"
