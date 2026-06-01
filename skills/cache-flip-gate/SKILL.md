---
name: "cache-flip-gate"
description: "Evaluate 30-day P50 of per-spawn cache read_ratio against the 0.70 flip threshold. Operator-invoked staged-flip gate that decides whether READ_RATIO_TARGET in skills/cache-audit/SKILL.md can be raised from 0.65 to 0.70. Advisory only — never gates a pipeline phase."
verdict: "CACHE_FLIP_GATE_PASS"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional: --metrics-root <path> (defaults to ~/.claude/metrics)"
---

# Cache Flip Gate

## When to Invoke

- **Operator request** after at least 30 days of cache observations have accumulated since Slice C shipped (2026-05-15). The skill answers a single yes/no question: is the harness sustaining P50 read_ratio ≥ 0.70 across ≥100 observations?
- **Adjacent to `/harness:cache-audit`**: `/harness:cache-audit` produces a snapshot report. This skill produces a flip-decision verdict.
- **Do NOT use** as a pipeline gate. This skill never blocks `/harness:build-implementation`, `/harness:code-review`, or any Final Gate skill. It informs a manual constant edit in `skills/cache-audit/SKILL.md`.

## Inputs

- **Filesystem**: `~/.claude/metrics/*/cache.jsonl` — same source as `/harness:cache-audit`. Each JSONL record carries `read_ratio` (float 0..1).
- **Pipeline state**: none.

## Procedure

### Step 1: Collect read_ratio observations

Glob all `cache.jsonl` files under the metrics root. Parse each line; collect every `read_ratio` field. Records older than 30 days are excluded (file mtime + line timestamp).

### Step 2: Classify

Apply the gate rules (implemented in `hooks/_lib/cache_flip_gate.py`):

| Condition | Verdict | Polarity |
|---|---|---|
| `n < 30` | `CACHE_FLIP_GATE_INSUFFICIENT_DATA` | info |
| `n >= 30` AND `P50 < 0.70` | `CACHE_FLIP_GATE_HOLD` | info |
| `n >= 100` AND `P50 >= 0.70` | `CACHE_FLIP_GATE_PASS` | success |

The asymmetry between the data threshold (n≥30 to grade) and the pass threshold (n≥100) is intentional: a small sample can confidently say "below threshold" but a larger sample is required to say "stably above threshold".

### Step 3: Emit verdict + payload

```json
{
  "verdict": "CACHE_FLIP_GATE_PASS",
  "n_observations": 142,
  "p50": 0.74
}
```

## Output Format

Single-line JSON to stdout. No markdown report; this is a programmatic gate.

## Safeguards

- **Advisory only.** Never modifies `skills/cache-audit/SKILL.md`. Operator manually edits the `READ_RATIO_TARGET` constant after seeing a `PASS` verdict.
- **Never auto-flips.** The 0.65 → 0.70 transition is a deliberate human-in-the-loop step. This skill produces evidence; humans decide.
- **Two-state evidence trail.** Operator must observe `PASS` twice (re-run separated by ≥7 days) before flipping, per `feedback_disclosure_is_not_deferral` — single-day P50 spikes do not justify a constant change.

## Verdict

```
Verdict: CACHE_FLIP_GATE_PASS | CACHE_FLIP_GATE_HOLD | CACHE_FLIP_GATE_INSUFFICIENT_DATA
Next: Operator reviews; manual constant edit only on PASS observed twice.
Artifacts: stdout JSON line (no file written).
```
