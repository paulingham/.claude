#!/usr/bin/env bash
# Dispatcher for the eval-capture hook: privacy gate + PR extraction + fork.
# Kept tiny so the hook itself stays under 50 lines and returns fast.

_ec_privacy_acked() {
  [ "${CLAUDE_EVAL_CAPTURE_ACKED:-0}" = "1" ] && return 0
  [ -f "eval/.privacy-acked" ]
}

_ec_extract_pr() {
  local cmd; cmd="$(jq -r '.tool_input.command // empty' 2>/dev/null)"
  printf '%s' "$cmd" | grep -oE 'gh pr merge[[:space:]]+[0-9]+' | awk '{print $NF}' | head -1
}

_ec_invoke_worker() {
  local pr="$1" worker="$HERE_ECM/_lib/eval-capture-worker.sh"
  if [ "${CLAUDE_EVAL_CAPTURE_NOFORK:-0}" = "1" ]; then
    bash "$worker" "$pr"; return 0
  fi
  nohup bash "$worker" "$pr" </dev/null >/dev/null 2>&1 & disown
}

eval_capture_dispatch() {
  local input pr
  input="$(cat)"
  _ec_privacy_acked || { echo "[eval-capture] privacy gate not acked — skipping" >&2; exit 0; }
  pr="$(printf '%s' "$input" | _ec_extract_pr)"
  [ -z "$pr" ] && exit 0
  _ec_invoke_worker "$pr"
  exit 0
}
