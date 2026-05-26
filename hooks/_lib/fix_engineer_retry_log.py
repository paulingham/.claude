"""Fix-engineer retry depth forensics emitter (AC6).

Emits one JSONL line to metrics/{session}/fix-engineer-retry.jsonl per
fix-engineer round. Schema pins 6 required fields.
"""
from jsonl_append import append_jsonl


def emit_retry_record(
    metrics_dir, task_id, round_idx, model_tier_before, model_tier_after,
    verdict, finding_count
):
    append_jsonl(metrics_dir, "fix-engineer-retry.jsonl", {
        "task_id": task_id,
        "round_idx": round_idx,
        "model_tier_before": model_tier_before,
        "model_tier_after": model_tier_after,
        "verdict": verdict,
        "finding_count": finding_count,
    })
