#!/usr/bin/env bash
# Download bge-small-en-v1.5 ONNX model into ~/.claude/models/.
# Prints export lines for ORT_DYLIB_PATH and BGE_MODEL_PATH plus the
# backfill hint. Idempotent: skips download if model.onnx exists.
#
# WARNING: the current ship does NOT consume this model. The real ORT
# backend lands in Story S5.1. See pipeline-state/claude-mem-port-s5.1-story.md.
set -euo pipefail

cat >&2 <<'WARN'
⚠ This model (~130MB) is downloaded for S5.1. The current ship does NOT
consume it — the real ORT backend is not yet implemented. Proceeding will
place the model on disk but no code path will load it until Story S5.1.
WARN

if [ -n "${CI:-}" ] || [ -n "${NONINTERACTIVE:-}" ]; then
  echo "abort: CI/NONINTERACTIVE set — rerun interactively or wait for S5.1" >&2
  exit 2
fi

printf "Continue? [y/N] " >&2
read -r ANSWER
case "${ANSWER}" in
  y|Y|yes|YES) ;;
  *) echo "aborted by user" >&2; exit 1 ;;
esac

MODEL_DIR="${HOME}/.claude/models/bge-small-en-v1.5"
MODEL_FILE="${MODEL_DIR}/model.onnx"
URL="${BGE_MODEL_URL:-https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/onnx/model.onnx}"

mkdir -p "${MODEL_DIR}"

if [ ! -f "${MODEL_FILE}" ]; then
  echo "Downloading bge-small-en-v1.5 to ${MODEL_FILE}..." >&2
  curl -fsSL "${URL}" -o "${MODEL_FILE}.partial"
  mv "${MODEL_FILE}.partial" "${MODEL_FILE}"
fi

DYLIB="${ORT_DYLIB_PATH:-/opt/homebrew/lib/libonnxruntime.dylib}"
if [ ! -f "${DYLIB}" ]; then
  echo "warn: ORT dylib not found at ${DYLIB} — brew install onnxruntime" >&2
fi

cat <<EOF
Embedder ready. Add to your shell profile:

  export ORT_DYLIB_PATH=${DYLIB}
  export BGE_MODEL_PATH=${MODEL_FILE}

Then backfill existing observations:

  python3 -m embedder backfill --db ~/.claude/db/memory.sqlite

Verify: python3 -m embedder cli doctor
EOF
