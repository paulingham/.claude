---
name: "internal-eval-capture"
description: "Sub-skill of /internal-eval. Turns real merged PRs into promoted eval cases. Populated by Story 4 (backfill + oracle detection) and Story 5 (auto-capture on merge)."
context: fork
agent: software-engineer
---

# Internal Eval — Capture

## Status

Stub. Populated by Story 4 (`backfill` + `promote` subcommands + oracle detection via `oracle-paths.json`) and Story 5 (post-merge auto-capture writing to `eval/cases/.candidates/`).

## Purpose

Produce promoted cases under `eval/cases/{case-id}/` from real merged PRs. Each case captures the PR's intent (prompt, oracle tests, expected diff) so the harness can be replayed against it deterministically.

## Subcommands (to be implemented)

- `backfill --limit N` — scan recent merged PRs, filter via `oracle-paths.json` allow-list, write candidates to `eval/cases/.candidates/`.
- `promote <case-id>` — move a candidate from `.candidates/` into `eval/cases/` (joins the active suite).

## Privacy Gate (Story 5)

Auto-capture writes ONLY to `.candidates/` (gitignored). Promotion requires either the committed marker `eval/.privacy-acked` OR `CLAUDE_EVAL_CAPTURE_ACKED=1` in the environment. Hook exits in <1s via a detached background job; bounded retention via `eval/capture.log`.

## Verdict

Populated by Story 4. Candidate verdicts will be `CAPTURED` | `PROMOTED` | `CAPTURE_SKIPPED`.
