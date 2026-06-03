"""WS-B — Agentic OWASP Top 10 security-checklist gating trigger.

The security-engineer review must apply the Agentic OWASP Top 10 checklist
(memory poisoning, instinct poisoning, tool misuse, goal hijacking) whenever a
change touches an agentic-control surface: `learning/`, `agent-memory/`, or
`hooks/`. This module is the pure decision core consumed by
`hooks/agentic-security-gate.sh`; keeping it import-clean makes the gating
trigger unit-testable without a subprocess.
"""
from __future__ import annotations

# The three agentic-control surfaces. A diff touching any of these requires the
# Agentic OWASP Top 10 checklist during security review.
AGENTIC_SURFACE_PREFIXES = ("learning/", "agent-memory/", "hooks/")

# Substring the spawn prompt must carry to prove the reviewer was directed to
# apply the agentic checklist. Matched case-insensitively.
_AGENTIC_PROMPT_MARKER = "agentic"

# Only this agent role is governed by the gate.
_GATED_AGENT = "security-engineer"


def _normalize(path):
    return path.strip().lstrip("./") if path else ""


def touches_agentic_surface(changed_files):
    """Return the sorted, de-duplicated agentic surfaces the changeset touches.

    Matching is segment-anchored on the path prefix: `hooks/x.sh` matches but
    `docs/hooks-guide.md` does not. Blank entries are ignored.
    """
    matched = set()
    for raw in changed_files or []:
        norm = _normalize(raw)
        if not norm:
            continue
        for prefix in AGENTIC_SURFACE_PREFIXES:
            root = prefix.rstrip("/")
            if norm == root or norm.startswith(prefix):
                matched.add(root)
    return sorted(matched)


def prompt_satisfies_gate(prompt):
    """True when the prompt directs the reviewer to apply the agentic checklist."""
    return _AGENTIC_PROMPT_MARKER in (prompt or "").lower()


def gate_decision(changed_files, prompt, *, subagent_type=_GATED_AGENT, disabled=False):
    """Compose the gate verdict.

    Returns {action, surfaces, reason} where action in {allow, block, bypass}.
    """
    surfaces = touches_agentic_surface(changed_files)
    if subagent_type != _GATED_AGENT:
        return {"action": "allow", "surfaces": surfaces, "reason": "agent not gated"}
    if not surfaces:
        return {"action": "allow", "surfaces": [], "reason": "no agentic surface touched"}
    if disabled:
        return {"action": "bypass", "surfaces": surfaces,
                "reason": "CLAUDE_DISABLE_AGENTIC_GATE=1"}
    if prompt_satisfies_gate(prompt):
        return {"action": "allow", "surfaces": surfaces,
                "reason": "agentic checklist directive present in spawn prompt"}
    return {
        "action": "block",
        "surfaces": surfaces,
        "reason": (
            "changeset touches agentic surface(s) [%s] but the spawn prompt lacks "
            "the Agentic OWASP Top 10 directive" % ", ".join(surfaces)
        ),
    }
