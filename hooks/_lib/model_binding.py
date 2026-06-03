"""Pure model-binding helpers — no I/O, no shell calls, no env reads.

Owns the emit/suppress decision and hookSpecificOutput JSON construction
for the advisor hook's model-binding feature (Slice A of WS-D).
"""
import json

__all__ = ["should_emit_model", "build_hook_output"]


def should_emit_model(mc_result: dict) -> bool:
    """Return True iff model binding should be emitted to CC.

    Emits only when resolve_model_conditional fired a conditional rule
    (source starts with 'rule-match:') AND the resolved model is non-empty.
    Conservative: default-arm, no-conditional, and no-budget paths all
    suppress emission — binding fires only when a rule genuinely overrides.
    """
    source = mc_result.get("source", "")
    model = mc_result.get("model")
    return source.startswith("rule-match:") and isinstance(model, str) and bool(model)


def build_hook_output(model: str) -> str:
    """Return the hookSpecificOutput JSON for a model binding.

    Produces the permissionDecision+updatedInput envelope that CC reads
    from a PreToolUse hook's stdout when it wants to rewrite the tool input.
    """
    payload = {
        "hookSpecificOutput": {
            "permissionDecision": "allow",
            "updatedInput": {"model": model},
        }
    }
    return json.dumps(payload)
