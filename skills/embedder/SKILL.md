---
name: embedder
description: Optional semantic rerank for recall. bge-small-en-v1.5 via ONNX Runtime C API. Default OFF.
---

# embedder — semantic rerank for claude-mem

## How it works

Capture writes observations; backfill encodes them to 384-d
L2-normalised vectors via bge-small-en-v1.5 running on ONNX Runtime
(C API, via stdlib ctypes). Recall asks `rerank.rerank` to blend the
cosine score against BM25 rank. The embedder is loaded lazily — the
default capture path never imports it (zero-cost invariant).

Pipeline per encode:

```
text → tokenizer.encode (WordPiece, stdlib) → int64 tensors
     → ort_session_run.run → last_hidden_state (1, seq_len, 384)
     → pool.mean_pool_l2 → 1536 bytes
```

## Requirements

Requires macOS or Linux. **Windows is not supported** — `ORTCHAR_T`
path encoding differs between POSIX and Windows, and this module
ships the POSIX (UTF-8 bytes) variant only. Use WSL on Windows.

The runtime needs:

- ONNX Runtime ≥ 1.17 (dynamic library installed — `brew install
  onnxruntime` on macOS, `apt install libonnxruntime-dev` on Linux)
- The bge-small-en-v1.5 ONNX file on disk (fetched by
  `download-model.sh`)

## Truncation: 128 tokens for capture, 512 for backfill

`tokenizer.encode(text, max_len=…)` pads and truncates to `max_len`.
Capture pads to 128 tokens (typical observation size, optimises for
encode latency). Backfill pads to 512 tokens (historical content may
include longer pasted logs or stacktraces). Content longer than
`max_len` is truncated server-side by the tokenizer.

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
    real.py          ORT C API binding
    paths.py         dylib + model resolution + typed exceptions
    cli_actions.py   probe/doctor/status/setup handlers
    doctor.py        6-field diagnostic + verdict rendering
    doctor_db.py     read-only unembedded_count
    doctor_probe.py  facade exercise → (ok, reason)
    doctor_verdict.py verdict computation
    backfill_batch.py INSERT OR REPLACE INTO embeddings (content_hash)
    backfill_cli.py  argparse + stdout summary formatter
```

## Setup

### macOS

```bash
# 1. Install ORT
brew install onnxruntime

# 2. Download the model (interactive gate — confirms you understand
#    the download size and license)
./skills/embedder/download-model.sh

# 3. Export the two required env vars (the script prints these)
export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib
export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx

# 4. Backfill existing observations
PYTHONPATH=skills python3 -m embedder backfill --db ~/.claude/db/memory.sqlite

# 5. Verify — doctor will show verdict: OK
PYTHONPATH=skills python3 -m embedder cli doctor
```

### Linux (Debian / Ubuntu)

```bash
# 1. Install ORT (apt ships libonnxruntime-dev on Ubuntu 22.04+; for older
#    distros fall back to the upstream .deb or a /usr/local build)
sudo apt-get install -y libonnxruntime-dev

# 2. Download the model
./skills/embedder/download-model.sh

# 3. Export env vars (the script prints these; detect-ort.sh resolves the
#    library path automatically — set ORT_DYLIB_PATH only to override)
export ORT_DYLIB_PATH=/usr/lib/x86_64-linux-gnu/libonnxruntime.so
export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx

# 4. Backfill + 5. Verify — same as macOS
PYTHONPATH=skills python3 -m embedder backfill --db ~/.claude/db/memory.sqlite
PYTHONPATH=skills python3 -m embedder cli doctor
```

Windows is not supported natively. Use WSL and follow the Linux path from inside the Linux shell.

## Test-only: CLAUDE_EMBEDDER=fake

**Warning.** FakeEmbedder produces hash-derived vectors. Rerank against
these equals noise — identical text hashes to the same vector but
paraphrases get unrelated vectors. It exists exclusively to prove the
capture/recall/backfill wiring works end-to-end against the embedder
contract (`encode(text) -> bytes` of length `4 * dim`). **Do not use in
production.** Treat it as a stub for wiring tests.

```bash
CLAUDE_EMBEDDER=fake PYTHONPATH=skills python3 -m embedder cli doctor   # tests only
```

## Bootstrap gates embedding

Capture-time embedding is gated on model file presence, not an env
flag. `/project-setup` downloads the model and writes
`ORT_DYLIB_PATH` + `BGE_MODEL_PATH` to `~/.claude/settings.json`. If
either path cannot be resolved to an existing file, `maybe_embed`
skips the embed without importing `embedder.*` (zero-cost invariant)
and emits a one-time stderr warning:

    embedder model not bootstrapped; semantic recall disabled.
    Run /project-setup to enable.

`embedder doctor` reports the gate state via an `embed:` line:

    embed: off (no model — run /project-setup)   # models missing
    embed: on (pending first write)              # present, no success yet
    embed: on                                    # present + last_success_at set

On corrupt-but-existing model, the capture path logs to
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
- **Zero-cost on missing models**: capture path does not import `embedder.embedder` unless both model files resolve.
- **Idempotent backfill**: second run inserts 0 rows (keyed by content_hash).
- **Stdlib only**: no pip install, no requirements.txt.
