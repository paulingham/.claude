#!/usr/bin/env bash
# Reflect-phase gate: halts when any named-deviation reflect token is
# unacknowledged.
#
# Usage: reflect-gate-acknowledgment.sh [token_dir]
#   token_dir defaults to $HOME/.claude/metrics/$CLAUDE_SESSION_ID/reflect-tokens
#
# Exit 0: no tokens OR all tokens have acknowledged=true (silent).
# Exit 1: one or more tokens have acknowledged=false OR malformed JSON.
#
# enforces: protocols/reflection-protocol.md § 6d-bis
# pairs with: hooks/reflect-token-emit.sh
# protects: Iron Law 6 (findings surfaced are fixed in-cycle)

set -u

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="${1:-$HOME/.claude/metrics/$SESSION/reflect-tokens}"

[[ -d "$DIR" ]] || exit 0

python3 - "$DIR" <<'PY'
import json, os, re, sys
d = sys.argv[1]
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
blockers, errors = [], []
for name in sorted(os.listdir(d)):
    if not name.endswith(".json"):
        continue
    p = os.path.join(d, name)
    try:
        with open(p) as fh:
            t = json.load(fh)
    except (OSError, ValueError) as e:
        errors.append(f"{name}: {e}")
        continue
    if t.get("acknowledged") is not True:
        did = t.get("deviation_id", name)
        rationale = _CTRL.sub("", t.get("rationale", ""))[:80] if t.get("rationale") else ""
        blockers.append((did, rationale))
if errors:
    sys.stderr.write("[Reflect gate] BLOCKED: malformed token file(s):\n")
    for e in errors:
        sys.stderr.write(f"  - {e}\n")
    sys.exit(1)
if blockers:
    sys.stderr.write(f"[Reflect gate] BLOCKED: {len(blockers)} unacknowledged named-deviation token(s):\n")
    for did, r in blockers:
        suffix = f": {r}" if r else ""
        sys.stderr.write(f"  - {did}{suffix}\n")
    sys.stderr.write("Operator must edit each token file to set acknowledged: true, then re-run /pipeline-resume.\n")
    sys.exit(1)
PY
