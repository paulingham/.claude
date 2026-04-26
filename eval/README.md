# Internal Eval Harness

Proprietary internal evaluation harness for the `~/.claude/` agentic harness itself.
Runs frozen, real-world cases (captured from merged PRs) against the current harness
to detect regressions and measure harness-level changes.

## Why this exists

The harness builds features by dispatching AI agents through a pipeline. Pipeline
changes (new rules, new skills, tweaked agent definitions, hook edits) can silently
degrade build quality. This harness replays representative historical PRs against the
current harness, scores the outputs, and flags regressions before they ship.

## Case Layout

Each case lives under `eval/cases/{case-id}/` with exactly these artifacts:

```
eval/cases/{case-id}/
  task.md          AC-style task description. NO golden-diff hints.
  context/         Pre-change source files. Populated by the capture CLI.
  expected.md      Specific behaviors + test names that MUST be green post-change.
  golden-diff/     The merged PR's actual diff, for reference + exact scoring.
  metadata.json    Case metadata (see SCHEMA.md in _example/).
```

See `eval/cases/_example/` for a fully documented schema example. Read `SCHEMA.md`
alongside it for per-field semantics.

## Directory Layout

```
eval/
  README.md                    This file
  cases/                       Committed: frozen eval cases (one per directory)
    _example/                  Schema reference (committed)
    .candidates/               Gitignored: PENDING cases awaiting curation
  runs/                        Gitignored: per-run working state + results
  baselines/                   Committed: baseline reports (harness-ref + score stamps)
```

## Contributing a Case Manually

Story 3 will land 3+ real curated cases (demonstrating the manual authoring flow).
Until then, the manual steps are:

1. Pick a merged PR with clear ACs and changed tests.
2. Copy `eval/cases/_example/` to `eval/cases/{your-case-id}/`.
3. Fill in `task.md` from the PR's description (AC-style, no file-path hints).
4. Populate `context/` with the pre-change versions of files the PR touched.
5. Drop the merged PR's `git diff` into `golden-diff/` (as a single `.patch` file).
6. List the test names that MUST be green post-change in `expected.md`.
7. Fill in `metadata.json` — especially `min_harness_ref` (the SHA the case was
   authored against; cases outside their compatibility window are SKIPPED, not failed —
   see Story 7/8).
8. Run `bash skills/internal-eval/tests/test_case_schema.sh` — must exit 0.
9. Commit.

Story 4 will provide a `capture` CLI that automates steps 2-7 from a merged PR URL.

## What's Gitignored vs Committed

| Path | Status | Rationale |
|------|--------|-----------|
| `eval/cases/{case-id}/` | Committed | Frozen cases are the input to the harness |
| `eval/cases/.candidates/` | **Gitignored** | PENDING auto-captured cases; curated, not shipped |
| `eval/runs/` | **Gitignored** | Local run state, per-case scratch, large artifacts |
| `eval/baselines/` | Committed | Baseline reports are the comparison target |
| `eval/README.md` | Committed | This file |

## Status

- **Story 1 (this story)**: Case format schema + directory scaffolding.
- **Stories 2-12**: Skill + capture/run/report CLIs + baselines + regression gate.
  See `pipeline-state/internal-eval-plan-validation.md` for the full plan.
