"""Mode-token mutual-exclusivity validator for patch-critic spawns.

Three patch-critic modes are mutually exclusive:

- **single-critic** (legacy default): no mode token in the prompt.
- **multi-persona** (#93): `Persona: <correctness|regression-risk|scope-creep>`.
- **tournament** (PDR-RTV Slice 2): `Mode: tournament` + `Candidates: A,B`.

Spawns carrying BOTH a `Mode: tournament` token AND a `Persona:` token are
`MODE_AMBIGUOUS` — the spawn-handling code path rejects them before the
agent receives the prompt. The orchestrator surfaces `MODE_AMBIGUOUS` as
`PATCH_REJECTED` and writes a forensic JSONL line at
`metrics/{session}/advisor-dispatch.jsonl` with `source: "mode-ambiguous"`.

This module is a pure validator — no I/O, no side effects. The caller
(`hooks/pre-agent-advisor.sh` via `resolve-mode-token.py`) is responsible
for emitting the JSONL forensic line via `log-injection.sh`.
"""
from __future__ import annotations

import re
from typing import Dict

# The three documented persona tokens. An unknown `Persona:` value falls
# through to single-critic mode rather than being treated as a persona —
# preserves legacy behaviour for prompts that mention "persona" colloquially.
_PERSONA_VALUES = ("correctness", "regression-risk", "scope-creep")

_MODE_TOURNAMENT = re.compile(r"^Mode:\s+tournament\s*$", re.MULTILINE)
_PERSONA_TOKEN = re.compile(
    r"^Persona:\s+(?P<value>\S+)\s*$", re.MULTILINE
)


def _find_tournament_token(prompt: str) -> str | None:
    """Return the literal `Mode: tournament` token if present."""
    if _MODE_TOURNAMENT.search(prompt):
        return "Mode: tournament"
    return None


def _find_persona_token(prompt: str) -> str | None:
    """Return the literal `Persona: <value>` token if a documented persona is present.

    Iterates over every `Persona:` line — an unknown-value line followed by a
    documented-value line still flags the documented one. Keeps unknown
    persona values inert (they fall through to single-critic) without
    blocking detection of a documented persona elsewhere in the prompt.
    """
    for match in _PERSONA_TOKEN.finditer(prompt):
        if match.group("value") in _PERSONA_VALUES:
            return f"Persona: {match.group('value')}"
    return None


def classify_mode(prompt: str) -> Dict[str, object]:
    """Classify a patch-critic spawn prompt into one of four mode states.

    Returns a dict with keys:
      mode   : one of "tournament" | "persona" | "single-critic" | "ambiguous"
      status : "ok" (passes guard) or "MODE_AMBIGUOUS" (dual-token guard fails)
      tokens : list of the literal offending tokens (empty for single-critic,
               one token for tournament/persona, two for ambiguous)
    """
    prompt = prompt or ""
    tournament_token = _find_tournament_token(prompt)
    persona_token = _find_persona_token(prompt)

    if tournament_token and persona_token:
        return {
            "mode": "ambiguous",
            "status": "MODE_AMBIGUOUS",
            "tokens": [tournament_token, persona_token],
        }
    if tournament_token:
        return {"mode": "tournament", "status": "ok", "tokens": [tournament_token]}
    if persona_token:
        return {"mode": "persona", "status": "ok", "tokens": [persona_token]}
    return {"mode": "single-critic", "status": "ok", "tokens": []}


__all__ = ["classify_mode"]
