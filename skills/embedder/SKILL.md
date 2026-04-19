---
name: embedder
description: Optional semantic rerank for recall. bge-small-en-v1.5 via ONNX Runtime C API. Default OFF.
---

# embedder — semantic rerank for claude-mem

## Current status: infrastructure only

Real ORT backend deferred to Story S5.1 (see
`pipeline-state/claude-mem-port-s5.1-story.md`). Today the module ships:

- **FakeEmbedder** (deterministic hash-derived vectors, **test-only** —
  hash-based rerank = noise, not semantic search)
- **Capture + recall + backfill wiring** that is backend-agnostic
- **Status/doctor diagnostics** (6-field output + verdict)

When S5.1 lands, set `ORT_DYLIB_PATH` + `BGE_MODEL_PATH` and the same
capture/recall paths gain real semantic rerank with no code changes.

Running `embedder doctor` today (with env unset) produces:

```
ORT_DYLIB_PATH: <unset>
BGE_MODEL_PATH: <unset>
last_error: ORT_DYLIB_PATH not set
last_error_at: 2026-04-19T…
last_success_at: <none>
unembedded_count: 0
verdict: UNAVAILABLE: ORT_DYLIB_PATH not set
```

That is the expected output until S5.1.

## Architecture

```
skills/embedder/
  embedder.py        singleton dispatch (CLAUDE_EMBEDDER=fake|real)
  status.py          atomic JSON writer — ~/.claude/state/embedder-status.json
  cli.py             doctor | status | setup
  backfill.py        batched embed-missing CLI (BEGIN IMMEDIATE per 100)
  download-model.sh  fetch bge-small-en-v1.5 ONNX (gated — S5.1 only)
  _lib/
    fake.py          deterministic hash-based FakeEmbedder (testing)
    real.py          ORT C API binding (deferred to S5.1)
    paths.py         dylib + model resolution + typed exceptions
    cli_actions.py   probe/doctor/status/setup handlers
    doctor.py        6-field diagnostic + verdict rendering
    doctor_db.py     read-only unembedded_count
    doctor_probe.py  facade exercise → (ok, reason)
    doctor_verdict.py verdict computation
    backfill_batch.py INSERT OR REPLACE INTO embeddings (content_hash)
    backfill_cli.py  argparse + stdout summary formatter
```

## Setup (S5.1 — not yet functional)

```bash
# 1. Install ORT
brew install onnxruntime

# 2. Download the model (interactive gate — confirms you understand
#    the model is not consumed until S5.1)
./skills/embedder/download-model.sh

# 3. Export the two required env vars (the script prints these)
export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib
export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx

# 4. Backfill existing observations
python3 -m embedder backfill --db ~/.claude/db/memory.sqlite

# 5. Verify — doctor will show verdict: OK once S5.1 ships
python3 -m embedder cli doctor
```

## Test-only: CLAUDE_EMBEDDER=fake

**Warning.** FakeEmbedder produces hash-derived vectors. Rerank against
these equals noise — identical text hashes to the same vector but
paraphrases get unrelated vectors. It exists exclusively to prove the
capture/recall/backfill wiring works end-to-end against the embedder
contract (`encode(text) -> bytes` of length `4 * dim`). **Do not use in
production.** Treat it as a stub for wiring tests.

```bash
CLAUDE_EMBEDDER=fake python3 -m embedder cli doctor   # tests only
```

## Opt-in at capture time

Default: capture path does NOT import the embedder module (zero-cost
invariant — verified by `test_live_writer_embed.py`).

```bash
export CLAUDE_EMBED_AT_CAPTURE=1   # embed on every PostToolUse write
```

On missing/corrupt model, the capture path logs to
`~/.claude/db/live-writer.log`, records the failure reason via
`status.record_failure`, and still writes the observation — the
embedding is skipped, not the observation.

## Privacy

Privacy is enforced at recall query time (is_private filter), not at
backfill or capture time. Backfill embeds every observation, including
is_private=1 rows, so flipping privacy mode later requires no rebuild.

## Recall integration

`skills/recall/recall.py` calls `rerank_support.apply()` on the top-K
lexical hits. If `CLAUDE_EMBEDDER` is unset, `apply()` returns the lexical
ordering and emits the banner:

    [recall: lexical-only — run 'embedder doctor' to enable semantic rerank]

The rerank score is `alpha/(1+idx) + (1-alpha)*cosine` with `alpha=0.5`.

## Invariants

- **Read-only recall**: `vec_store.load` opens `?mode=ro` + `PRAGMA query_only=1`.
- **Default zero-cost**: default capture writes do not import `embedder.embedder`.
- **Idempotent backfill**: second run inserts 0 rows (keyed by content_hash).
- **Stdlib only**: no pip install, no requirements.txt.
