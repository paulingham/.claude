---
name: "internal-eval-capture"
description: "Sub-skill of /internal-eval. Turns real merged PRs into promoted eval cases via backfill + oracle detection. Populated by Story 4."
context: fork
agent: software-engineer
---

# Internal Eval — Capture

## Entry Points

| Script | Invoked as | Purpose |
|---|---|---|
| `backfill.sh` | `/internal-eval capture backfill [--limit N] [--since YYYY-MM-DD]` | Scan recent merged PRs, filter via `oracle-paths.json`, write candidates to `eval/cases/.candidates/` |
| `promote.sh` | `/internal-eval capture promote <case-id>` | Move candidate from `.candidates/` into `eval/cases/` (joins the active suite) |

## Process

### `backfill.sh`
1. **Privacy gate**: refuses to run unless `eval/.privacy-acked` exists (first run prints a banner explaining what will be captured).
2. **List merged PRs**: `gh pr list --state merged --search "merged:>${SINCE}" --limit "${LIMIT}"`.
3. **Oracle detection**: per-PR, runs `gh pr diff N --name-only` and matches against `oracle-paths.json` include globs. Zero matches ⇒ excluded.
4. **Candidate authoring**: for each surviving PR, calls `lib/gh-pr-to-case.sh` to produce the 5 artifacts (`task.md`, `context/`, `expected.md`, `golden-diff/pr-N.patch`, `metadata.json`).
5. **Exclusion report**: writes `eval/.candidates/.exclusion-report-{ISO-timestamp}.md` naming every skipped PR and the reason.
6. **Sparsity warning**: if `eval/cases/` + `eval/cases/.candidates/` cumulative total is `< 30`, emits a WARN line suggesting higher `--limit` or hand-authored cases.

### `promote.sh`
1. Validate source dir exists.
2. Validate destination does NOT exist (never overwrite).
3. Validate `metadata.json` (valid JSON + required fields via jq).
4. `mv` source → destination atomically.

## Files

- `oracle-paths.json` — include/exclude globs (Amendment A6 defaults)
- `lib/privacy.sh` — privacy banner + gate
- `lib/oracle-match.sh` — glob-based path matcher
- `lib/slug.sh` / `lib/slug_fn.sh` — PR-title → kebab-case slug
- `lib/meta.sh` — metadata.json assembly (classification inference, PR URL, min_harness_ref)
- `lib/gh-pr-to-case.sh` — PR → 5 artifacts helper
- `lib/backfill-run.sh` — the orchestrating loop

## Privacy Gate (Story 5)

Auto-capture writes ONLY to `.candidates/` (gitignored). Promotion requires either the committed marker `eval/.privacy-acked` OR `CLAUDE_EVAL_CAPTURE_ACKED=1` in the environment. Hook exits in <1s via a detached background job; bounded retention via `eval/capture.log`.

## Testing

`skills/internal-eval/tests/test_backfill.sh` exercises the flow with a `gh` shim at `skills/internal-eval/tests/_mocks/gh` that reads canned fixtures from `_mocks/fixtures/{fixture}-{kind}.{json,txt}`. No real `gh` calls.

## Verdict

- `CAPTURED` — candidate written to `.candidates/`
- `PROMOTED` — candidate moved into active suite
- `CAPTURE_SKIPPED` — no oracle match / excluded
