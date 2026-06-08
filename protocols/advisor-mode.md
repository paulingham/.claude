# Advisor-Mode Reviews (Opus 4.7)

Detail prose for the Advisor-Mode Reviews mechanism — the Sonnet-executor + Opus-advisor pairing for `code-reviewer` and `security-engineer`. CLAUDE.md keeps only a pointer.

## Mechanism

`code-reviewer` and `security-engineer` ship with `executor: claude-sonnet-4-6` + `advisor: claude-opus-4-7` in their frontmatter. Sonnet drives the review, Opus is consulted on judgement calls. This is the **intended default** for review work — review pairings remain **advisory at v2.1.140** because the `advisor:` field is **not yet schema-exposed** on the Agent tool input.

## Status (v2.1.140)

The `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl`; no spawn is blocked, and no model is downgraded. The advisor field is parsed from the agent's frontmatter and recorded for forensic visibility only.

The `advisor:` field remains not yet schema-exposed. Full advisor pairing (Sonnet-executor + Opus-advisor) remains advisory at v2.1.140. The `model` param IS now bound via `hookSpecificOutput.updatedInput.model` when the advisor resolver (`hooks/_lib/advisor_resolver.py::resolve_model_conditional`) yields `source == rule-match:*` (a conditional rule fires). Takes effect iff CC honors `updatedInput` on the Agent matcher (unverified at author time). Suppressed by `CLAUDE_DISABLE_MODEL_BINDING=1`.

## Cost Estimate (PROVISIONAL)

Pending advisor-baseline measurement (see `eval/baselines/{latest}-advisor-baseline.md`):

- (PROVISIONAL) Sonnet+Opus-advisor pairing is roughly ~40% cheaper per review than naive Opus-solo.
- Quality-equivalence target: ≥95% verdict-agreement on the regression suite. Not yet measured.

## Operator Controls

- `CLAUDE_REVIEW_ADVISOR_DISABLED=1` — force Opus-solo for the current session (escape hatch when the advisor pairing produces noisy verdicts on a specific run).
- `CLAUDE_DISABLE_ADVISOR_GATE=1` — short-circuit `hooks/pre-agent-advisor.sh` to `exit 0` before invoking the resolver. Mirrors `CLAUDE_DISABLE_TOOL_ALLOWLIST` and `CLAUDE_DISABLE_THINKING_GATE`. Use when a future enforcement flip mis-classifies a legitimate spawn; the hook becomes inert for the affected session and no `advisor-dispatch.jsonl` line is appended.
- `CLAUDE_DISABLE_MODEL_BINDING=1` — suppress `hookSpecificOutput.updatedInput.model` emission for the current session. JSONL logging is preserved. Use when model binding conflicts with a manual override.

## Scope

Applies only to `code-reviewer` and `security-engineer`. All other review/critic roles (`patch-critic`, `product-reviewer`, `qa-engineer`) ship without an advisor pairing — their default models are governed by `protocols/thinking-defaults.md` and the Agent Team table in CLAUDE.md.

## model_conditional Schema

The `model_conditional` frontmatter block layers complexity-budget-aware model routing on top of the static `model:` / `executor:` / `advisor:` triple. The block is **advisory at v2.1.140** — the resolver function `resolve_model_conditional()` in `hooks/_lib/advisor_resolver.py` is pure and exercised by unit tests. Bash-wrapper integration into `pre-agent-advisor.sh` is implemented in this release (WS-D bind-thinking-routing).

### Frontmatter fields

| Field | Type | Purpose |
|---|---|---|
| `default` | object | Arm returned when no rule matches OR budget is unavailable. Shape: `{model, executor, advisor}`. |
| `rules[]` | list | Ordered list of conditional arms; first match wins. |
| `rules[].when` | object | Match predicate. Currently supports `budget_lt: N` only. |
| `rules[].model` / `executor` / `advisor` | strings | Arm contents. `advisor: none` (literal string) drops the advisor pairing for this arm. |
| `status` | string | One of `advisory` (log-only) or `enforced`. v2.1.140 ships `advisory` only. |

### Resolver source enum

`resolve_model_conditional(frontmatter, budget)` returns `{model, executor, advisor, source}` where `source` is one of:

- `no-conditional` — frontmatter has no `model_conditional` key; top-level triple is returned.
- `no-budget` — budget is `None` / unavailable; the `default` arm is returned.
- `rule-match:budget_lt:N` — the first `rules[]` entry whose `when.budget_lt = N` matched.
- `default-arm` — `model_conditional` was present and budget was known, but no rule matched.

### Reference implementation

The canonical resolver lives at `hooks/_lib/advisor_resolver.py::resolve_model_conditional`. It is pure (no `open`, no `subprocess`, no `os.environ` reads) so it can be unit-tested directly via `inspect.getsource`. Bash-wrapper integration into `pre-agent-advisor.sh` is implemented in this release.

