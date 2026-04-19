---
role: software-engineer
phase: build
task_id: claude-mem-port-s6
slice: 0
timestamp: 2026-04-19T21:00:00Z
audit: complete
---

# S6 Slice 0 — Write-surface audit (observations + scratchpad_findings)

## Method

1. Recursive grep for `INSERT INTO observations`, `INSERT INTO scratchpad_findings`, `rows.INSERT_SQL`, `rows.row_from_obj`, `live_writer.`
2. Recursive grep for any `con.execute(.*INSERT` statement against these tables
3. Recursive grep for literal string `<private>` across test corpus (R10 mitigation)
4. Recursive grep for every `from _lib import ... rows` or `from _lib.rows` to locate transitive callers

Root grepped: entire worktree.

## Observations table — write surfaces

| # | Call site | Type | Production? | Routes through `privacy.apply`? (post-S6) |
|---|---|---|---|---|
| O1 | `skills/reindex-memory/_lib/live_writer.py::_insert` | PostToolUse hook → live capture | **YES** | Will call `privacy.apply` as first line of `_insert` (Slice 5) |
| O2 | `skills/reindex-memory/_lib/ingest.py::_insert_row` | Replay / reindex-from-JSONL | **YES** | **Must also call `privacy.apply`** — Slice 5 integrates at the single shared helper to guarantee parity |
| O3 | `tests/test_doctor_retrofit.py::87` | Direct `INSERT INTO observations` | Test only | Exempt — fixture constructs deliberately shaped row |
| O4 | `tests/test_embedder_backfill.py::84` | Direct `INSERT INTO observations` | Test only | Exempt — fixture |
| O5 | `tests/test_recall.py::238` | Direct `INSERT INTO observations` | Test only | Exempt — fixture |
| O6 | `tests/_support.py::_insert_private_observation` | Test helper (seeds private row) | Test only | Exempt — fixture sets `is_private=1` explicitly |

**Shared helper:** `skills/reindex-memory/_lib/rows.py::row_from_obj` + `rows.INSERT_SQL`. Both O1 and O2 call `rows.row_from_obj(obj, path)` before executing INSERT. Applying `privacy.apply(obj)` **before** `rows.row_from_obj` at both call sites guarantees identical `content_hash` + `searchable_text` — this is the dedup-integrity guarantee (R9).

**Decision:** We will invoke `privacy.apply(obj)` at the top of both `live_writer._insert` AND `ingest._insert_row`. Since `row_from_obj` reads `obj["file"]` for the `content_hash` composite, sanitizing `obj` in place before the helper call ensures live + replay paths produce identical hashes.

## Scratchpad findings table — write surfaces

| # | Call site | Type | Production? | Routes through `privacy.apply`? (post-S6) |
|---|---|---|---|---|
| S1 | `tests/_support.py::insert_scratchpad_rows` | Test helper | Test only | Exempt — explicit fixture |

**NO PRODUCTION SCRATCHPAD INGEST PATH EXISTS.** Scratchpad findings are currently authored as markdown files in `pipeline-state/{task-id}-scratchpad/*.md` (per the global playbook) and are not yet ingested into `scratchpad_findings` by any harness code. The schema table + FTS5 virtual table exist (from S1) but no production writer populates them.

**Implication for Slice 5b (AC2b):**
- AC2b says "Scratchpad write path with `body` containing `<private>shh</private>` results in a `scratchpad_findings` row whose `body` column contains neither the tag nor its contents, and `is_private = 0`. End-to-end test through the scratchpad ingest path."
- Since no production ingest path exists, Slice 5b must introduce one. The minimal introduction is a new library function (`live_writer.write_finding(obj, db_path)`) that mirrors `write_one` for observations and routes through `privacy.apply`. This is the canonical INSERT surface for scratchpad going forward.
- Shape budget: the new function is ≤5 lines, the INSERT SQL lives in a `findings.py` module alongside `rows.py`, and the existing test helper `tests/_support.py::insert_scratchpad_rows` is left untouched (it serves tests that exercise the schema directly, not the capture path).

**Integrity check post-Slice-5b:** Because no pre-existing production code writes to `scratchpad_findings`, there is no dedup drift risk — S6 is authoritative on the write path from day one.

## `<private>` literal in test corpus

Grep result: **zero matches** across the entire worktree (outside this audit file and the plan/story). No fixtures need updating before Slice 5. R10 drops out.

## Replay-path parity gate (R9)

The `content_hash` for a given `(session_id, timestamp, tool, file)` must match whether the row arrives via live-capture (live_writer) or reindex-from-JSONL (ingest). Because both paths share `rows.row_from_obj`, applying `privacy.apply(obj)` upstream of that shared helper is sufficient to preserve parity. Slice 5 adds an explicit test asserting identical `content_hash` and identical `is_private` for the same envelope processed through both paths.

## Summary

- **O1 and O2** are the only production write surfaces for `observations`. Both share `rows.row_from_obj`. Single intercept point: call `privacy.apply(obj)` before that helper in both call sites.
- **S1** is the only scratchpad INSERT, and it is test-only. Slice 5b introduces the first production scratchpad writer (`live_writer.write_finding`), which routes through `privacy.apply`.
- **Zero `<private>` literals** in existing tests — no fixture surgery needed.
- **Dedup integrity** preserved by applying sanitization before `row_from_obj` at both O1 and O2 call sites, verified by the Slice 5 parity test.

## HARD GATE SATISFIED

Audit artefact committed before any Slice-1+ code. Enumeration is complete, exemptions are justified, replay-path parity strategy is documented, and the test corpus is confirmed clean of literal `<private>`.
