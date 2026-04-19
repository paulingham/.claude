#!/usr/bin/env bash
# Download bge-small-en-v1.5 ONNX model into ~/.claude/models/.
# Prints export lines for ORT_DYLIB_PATH and BGE_MODEL_PATH plus the
# backfill hint. Idempotent: skips download if model.onnx exists.
set -euo pipefail

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
