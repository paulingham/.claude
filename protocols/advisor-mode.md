# Advisor-Mode Reviews (Opus 4.7)

Detail prose for the Advisor-Mode Reviews mechanism — the Sonnet-executor + Opus-advisor pairing for `code-reviewer` and `security-engineer`. CLAUDE.md keeps only a pointer.

## Mechanism

`code-reviewer` and `security-engineer` ship with `executor: claude-sonnet-4-6` + `advisor: claude-opus-4-7` in their frontmatter. Sonnet drives the review, Opus is consulted on judgement calls. This is the **intended default** for review work — review pairings remain **advisory at v2.1.140** because the `advisor:` field is **not yet schema-exposed** on the Agent tool input.

## Status (v2.1.140)

The `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl`; no spawn is blocked, and no model is downgraded. The advisor field is parsed from the agent's frontmatter and recorded for forensic visibility only.

Will become the enforced default the moment the `advisor:` field lands on the Agent tool input schema.

## Cost Estimate (PROVISIONAL)

Pending advisor-baseline measurement (see `eval/baselines/{latest}-advisor-baseline.md`):

- Sonnet+Opus-advisor pairing is roughly ~40% cheaper per review than naive Opus-solo.
- Quality-equivalence target: ≥95% verdict-agreement on the regression suite. Not yet measured.

## Operator Controls

- `CLAUDE_REVIEW_ADVISOR_DISABLED=1` — force Opus-solo for the current session (escape hatch when the advisor pairing produces noisy verdicts on a specific run).

## Scope

Applies only to `code-reviewer` and `security-engineer`. All other review/critic roles (`patch-critic`, `product-reviewer`, `qa-engineer`) ship without an advisor pairing — their default models are governed by `protocols/thinking-defaults.md` and the Agent Team table in CLAUDE.md.
