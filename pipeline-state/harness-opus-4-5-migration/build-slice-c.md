---
task_id: harness-opus-4-5-migration
slice: slice-c-cache-anchor-threshold-and-gate
phase: build
verdict: BUILD_COMPLETE
branch: feat/harness-opus-4-5-migration/slice-c
red_commit: 42d732d
green_commit: 07a2924
test_count_red: 9
test_count_green: 9
mutation_score: not_run
mutation_reason: harness lacks per-file mutation tooling at v2.1.140; advisory check at code-review
---

# Slice C Build Report — BUILD_COMPLETE

## Scope Shipped

All 5 ACs from plan.md Slice C section:

- **C.1**: Promoted `persona-tail` anchor from `deferred` to `advisory` in `hooks/_lib/resolve-cache-breakpoints.py`. Anchor now emits with `ttl: 1h` and `reason: promoted-slice-c-2026-05-15`.
- **C.2**: Added `## Small-agent skip list` subsection to `skills/cache-audit/SKILL.md` enumerating `planning-agent` (~1.4K tok), `sandbox-verify-engineer` (~1.3K tok), `vlm-critic` (~1.9K tok). Empirical verification: each prelude wc -c divided by ~4 chars/token gives the token estimate; all well under 4096-token API minimum cacheable threshold.
- **C.3 (ESCALATED)**: Appended `## Slice C ESCALATION — SDK flag (2026-05-15)` section to `protocols/cost-discipline.md` with literal tokens `SDK flag — consumer outside repo` and `the in-tree wire emission shipped 2026-05-15`.
- **C.4**: Raised `READ_RATIO_TARGET = 0.65` in `skills/cache-audit/SKILL.md` (three places: § Step 1 constant, § Output Format example skeleton, § Safeguards prose). Minted `skills/cache-flip-gate/SKILL.md` + `hooks/_lib/cache_flip_gate.py` (57 LOC, stdlib only). Added three verdicts to `rules/verdict-catalog.md`: `CACHE_FLIP_GATE_PASS` / `CACHE_FLIP_GATE_HOLD` / `CACHE_FLIP_GATE_INSUFFICIENT_DATA`.
- **C.5**: `hooks/_lib/resolve-cache-breakpoints.py` emits `cache_flag: true` in the resolved payload at the top level (sibling of `anchors[]`). `hooks/cache-breakpoint-injector.sh` is unchanged — it already pipes the resolved payload through `log-injection.sh`, which writes the entire payload under `resolved.*` in the JSONL record.

## Test Counts

- RED-first stubs: 9 (all failed at commit `42d732d` — see "Confirmed RED" section below)
- GREEN at commit `07a2924`: 9 / 9
- Broader regression on `tests/test_cache*.py`: 11 / 11 passing
- Broader regression on `tests/test_verdict*.py`: 3 / 3 passing
- Full Python suite: 2009 tests, 56 pre-existing failures (none touch slice-c files), 11 skipped — baseline unchanged from main

## Confirmed RED → GREEN

Each test failed at RED commit (`42d732d`), passes at GREEN commit (`07a2924`):

1. `tests/test_cache_breakpoints.py::test_persona_tail_anchor_active` — persona-tail status was "deferred", now "advisory".
2. `tests/test_cache_audit_small_agent_skip.py::test_small_agent_skip_list_documented` — section absent, now present with all 3 agents enumerated.
3. `tests/test_protocols_doc_references.py::test_sdk_flag_consumer_outside_repo_documented` — escalation prose absent, now present with both literal tokens.
4. `tests/test_cache_audit_read_ratio_target_constant.py::test_target_raised_to_0_65` — constant was 0.60, now 0.65; no rival thresholds in body.
5. `tests/test_cache_flip_gate.py::test_gate_emits_pass_when_p50_above_threshold` — module missing, now present; P50=0.72 + n=150 → PASS.
6. `tests/test_cache_flip_gate.py::test_gate_emits_hold_when_below_threshold` — P50=0.62 → HOLD.
7. `tests/test_cache_flip_gate.py::test_gate_emits_insufficient_when_n_below_30` — n=20 → INSUFFICIENT_DATA.
8. `tests/test_verdict_catalog_new_entries.py::test_cache_flip_gate_verdicts_in_catalog` — three verdicts present in catalog table, each row attributes `cache-flip-gate` emitter.
9. `tests/test_cache_breakpoint_injector_wire.py::test_jsonl_emits_cache_flag_token` — hook + resolver emit `resolved.cache_flag == true` in JSONL.

## Files Touched

```
modified: hooks/_lib/resolve-cache-breakpoints.py     (+12 -8)
modified: skills/cache-audit/SKILL.md                  (+27 -10)
modified: rules/verdict-catalog.md                     (+3 -0)
modified: protocols/cost-discipline.md                 (+5 -0)
created:  hooks/_lib/cache_flip_gate.py                (57 LOC)
created:  skills/cache-flip-gate/SKILL.md              (56 LOC)
created:  tests/test_cache_breakpoints.py              (44 LOC)
created:  tests/test_cache_audit_small_agent_skip.py   (37 LOC)
created:  tests/test_protocols_doc_references.py       (31 LOC)
created:  tests/test_cache_flip_gate.py                (57 LOC)
created:  tests/test_verdict_catalog_new_entries.py    (29 LOC)
created:  tests/test_cache_breakpoint_injector_wire.py (50 LOC)
updated:  tests/test_cache_audit_read_ratio_target_constant.py  (rewrote to assert 0.65)
```

## Deviations from Plan

- **Test file naming for C.5 wire emission**: Plan named `tests/test_hook_injection_schema.py` (also referenced by Slice B for B.4). Since that file does not exist in Slice C's branch (it is owned by Slice B and ships from the Slice B worktree), I created a dedicated file `tests/test_cache_breakpoint_injector_wire.py` for the C.5 test only. No conflict at merge — different filenames, no shared content.
- **Test file `test_protocols_doc_references.py`**: This file is named in BOTH the Slice B plan (B.3 escalation) and the Slice C plan (C.3 escalation). Per the build-orchestration brief from the prompt, I shipped only the C.3 test (`test_sdk_flag_consumer_outside_repo_documented`). The orchestrator must reconcile with Slice B's `test_beta_header_*` test at merge time. **Reconciliation note**: both tests are independent doc-prose-reference assertions on disjoint protocol files (`cost-discipline.md` for C, `thinking-defaults.md` for B); merging is a simple superset union — Slice B's branch will add its test method to the same `unittest.TestCase` or a sibling class.
- **Disclosure paragraph updated**: The `## Disclosure` section in `cache-audit/SKILL.md` previously enumerated three deferred anchors including `persona-marker-deferred`. Since C.1 promotes persona-tail to advisory, the disclosure now correctly reads "Two anchors are deferred" and explicitly states the promotion happened in Slice C (2026-05-15). This was not enumerated as a plan AC but is required for internal consistency — the old disclosure would have lied to operators after C.1 ships.
- **`cache_flag` placement**: Plan C.5 said the hook emits the field. The cleanest path was to add it at the resolver level (one Python file edit, picked up automatically by the bash hook that pipes the resolver output to log-injection.sh). No bash changes needed.

## Mutation Gap

No mutation tooling is configured at the harness layer for individual Python files in `hooks/_lib/`. The cache-flip-gate code is small (3 helper functions, 1 public entry) and exhaustively covered by the three behavior tests (PASS / HOLD / INSUFFICIENT). Code-review can advise on adequacy.

## Cohesion Check

- `hooks/_lib/cache_flip_gate.py`: 57 LOC, 3 private helpers + 1 public `evaluate()`. Each function does one thing (collect / classify / dispatch). Nesting depth ≤ 2.
- `hooks/_lib/resolve-cache-breakpoints.py`: 79 LOC, structure preserved from Slice A baseline. Persona-tail anchor moved out to its own module-level constant `_PERSONA_TAIL_ANCHOR` (consistent with existing `_DEFERRED_ANCHORS` pattern).

## SHAs

- Branch: `feat/harness-opus-4-5-migration/slice-c`
- Base (slice-a tip cherry-picked): `5767dd3`
- WIP-RED: `42d732d` (test stubs only, 9 failures confirmed)
- GREEN: `07a2924` (implementation, all 9 tests pass)
- Build-state commit: pending after this file is written

## Iron-Law Audit

- IL1 (ATDD): RED-first; 9 stubs confirmed failing at `42d732d`; all GREEN at `07a2924`.
- IL3 (orchestrator does not write code): N/A — this is the software-engineer agent.
- IL4 (main HEAD unchanged): All work on `feat/harness-opus-4-5-migration/slice-c` in worktree `agent-e81b1486`. Main HEAD remains `1d557dd`.
- IL6 (no follow-ups): Disclosure paragraph update in `cache-audit/SKILL.md` shipped in-cycle (would otherwise contradict C.1's anchor promotion). No deferred items.

## Verdict

```
BUILD_COMPLETE
```
