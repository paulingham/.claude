#!/usr/bin/env bash
# Download bge-small-en-v1.5 ONNX model into ~/.claude/models/.
# Prints export lines for ORT_DYLIB_PATH and BGE_MODEL_PATH plus the
# backfill hint. Idempotent: skips download if model.onnx exists.
set -euo pipefail

cat >&2 <<'WARN'
⚠ bge-small-en-v1.5 (~130MB) will be placed on disk. The real ORT backend
consumes this model for semantic rerank (see SKILL.md). Requires macOS or
Linux — Windows is not supported; use WSL.
WARN

if [ -n "${CI:-}" ]; then
  echo "abort: CI set — rerun interactively" >&2
  exit 2
fi

if [ -z "${NONINTERACTIVE:-}" ]; then
  printf "Continue? [y/N] " >&2
  read -r ANSWER
  case "${ANSWER}" in
    y|Y|yes|YES) ;;
    *) echo "aborted by user" >&2; exit 1 ;;
  esac
fi

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

if [ -n "${NONINTERACTIVE:-}" ]; then
  echo "model ready: ${MODEL_FILE}"
  exit 0
fi

cat <<EOF
Embedder ready. Add to your shell profile:

  export ORT_DYLIB_PATH=${DYLIB}
  export BGE_MODEL_PATH=${MODEL_FILE}

Then backfill existing observations:

  python3 -m embedder backfill --db ~/.claude/db/memory.sqlite

Verify: python3 -m embedder cli doctor

If 'claude-mem embedder doctor' reports 'verdict: UNHEALTHY',
delete the model and re-run this script:

  rm -rf "${MODEL_DIR}" && ./skills/embedder/download-model.sh
EOF
