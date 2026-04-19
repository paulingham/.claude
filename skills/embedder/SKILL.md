---
name: embedder
description: Optional semantic rerank for recall. bge-small-en-v1.5 via ONNX Runtime C API. Default OFF.
---

# embedder — semantic rerank for claude-mem

Composable, opt-in semantic layer on top of the lexical recall skill.
Zero PyPI dependencies (stdlib ctypes + struct). Zero impact on the default
capture/recall path — both paths skip embedder entirely unless opted in.

## Architecture

```
skills/embedder/
  embedder.py        singleton dispatch (CLAUDE_EMBEDDER=fake|real)
  status.py          atomic JSON writer — ~/.claude/state/embedder-status.json
  cli.py             doctor | status | setup
  backfill.py        batched embed-missing CLI (BEGIN IMMEDIATE per 100)
  download-model.sh  fetch bge-small-en-v1.5 ONNX file
  _lib/
    fake.py          deterministic hash-based FakeEmbedder (testing)
    real.py          ORT C API binding (deferred — see NOTE in source)
    paths.py         dylib + model resolution + typed exceptions
    cli_actions.py   probe/doctor/status/setup handlers
    backfill_batch.py INSERT OR REPLACE INTO embeddings (content_hash)
    backfill_cli.py  argparse + stdout summary formatter
```

## Setup

```bash
# 1. Install ORT (Homebrew — other platforms: see onnxruntime.ai)
brew install onnxruntime

# 2. Download the model
./skills/embedder/download-model.sh

# 3. Export the two required env vars (the script prints these)
export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib
export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx

# 4. Backfill existing observations
python3 -m embedder backfill --db ~/.claude/db/memory.sqlite

# 5. Verify
python3 -m embedder cli doctor
# embedder doctor: ok (bge-small-en-v1.5)
```

## Opt-in at capture time

Default: capture path does NOT import the embedder module (zero-cost
invariant — verified by `test_live_writer_embed.py`).

```bash
export CLAUDE_EMBED_AT_CAPTURE=1   # embed on every PostToolUse write
```

On missing/corrupt model, the capture path logs to
`~/.claude/db/live-writer.log` and still writes the observation — the
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
