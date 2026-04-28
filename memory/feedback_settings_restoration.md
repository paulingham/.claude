---
name: settings.json env restoration (wave4-R)
description: Restored adaptive thinking + 1M context on Opus 4.7; migrated subagent-model alias from "opus" to "default".
type: feedback
date: 2026-04-28
task_id: wave4-R
---

## What Was Restored

Removed two suppression flags and renamed the subagent-model alias in `settings.json` env block:

- DELETED `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING="1"` — adaptive thinking re-enabled.
- DELETED `CLAUDE_CODE_DISABLE_1M_CONTEXT="1"` — 1M-token context re-enabled.
- CHANGED `CLAUDE_CODE_SUBAGENT_MODEL` from `"opus"` to `"default"` — let the harness defaulting logic (per-agent `model:` frontmatter + `/eval-model-effectiveness` recommendations) decide, rather than pinning every spawn to opus.

## Why

Opus 4.7 (GA 2026-04-16) is materially better at adaptive thinking and long-context retrieval than the version those flags were originally added to suppress. The flags were defensive hardening for known regressions in an earlier model — those regressions no longer apply. Keeping the suppressions live wastes the model's strongest capabilities and biases the harness toward shallower, shorter-context reasoning than the agents are now trusted to perform.

The model alias migration `"opus"` → `"default"` shifts subagent model selection from a global override to per-role frontmatter + recommendation reports (what `/eval-model-effectiveness` produces). Pinning to `"opus"` made every recommendation moot.

## Revisit Conditions

- A documented Opus version regression where adaptive thinking measurably degrades. Concrete signal: `eval/baselines/{latest}-opus-X.md` shows >=10% drop on the adaptive-thinking evals. Re-add `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING="1"` until the next stable.
- A documented 1M-context regression: high-confidence retrieval failures inside the 200k–1M window on stable eval cases. Re-add `CLAUDE_CODE_DISABLE_1M_CONTEXT="1"`.
- A model-recommendations report showing `"default"` routing gives materially worse outcomes than pinned `"opus"` on critical pipelines.
- New Anthropic guidance explicitly recommending the suppression flags for a future model version.

## What Stayed

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS="1"` — still required.
- `CLAUDE_PIPELINE_MODE="autonomous"` — orthogonal.
- `CLAUDE_ENABLE_TRACE="1"` — orthogonal.
- All resource bounds (depth, runtime caps) — orthogonal.
