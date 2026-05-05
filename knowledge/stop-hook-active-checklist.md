# Stop / SubagentStop Hook Checklist

Every new hook in this repo registered on `Stop` or `SubagentStop` MUST satisfy this checklist before merge.

Canonical contract: <https://code.claude.com/docs/en/hooks> (sections "Stop" and "SubagentStop").

## Why this checklist exists

The `stop_hook_active` field is the harness's only signal that a Stop or SubagentStop event is firing inside a nested call (one Stop hook spawned a subagent, blocked Claude from stopping, or recursively invoked `claude`, and the resulting nested completion is now firing a second wave of hooks). The canonical docs are explicit:

> The `stop_hook_active` field is a boolean indicating whether Stop hooks are currently executing. This field helps prevent infinite loops: if your Stop hook calls `claude` recursively or spawns a subagent, that nested call's Stop hooks will see `stop_hook_active: true`. **Use this to skip expensive operations or logging in nested calls.**

A hook that ignores it can:

1. **Loop infinitely** — if it returns `{"decision": "block"}` and the block triggers another Stop, the new Stop fires the same hook, which blocks again, forever.
2. **Recurse unboundedly** — if the hook spawns a subagent or invokes `claude`, each child finishes and refires the hook, geometrically.
3. **Pollute forensic state** — duplicate trajectory rows, duplicate cost records, duplicate context messages, double-fired auto-learn triggers, double cleanup of runtime-guard files.

The first two are catastrophic; the third is the common case in this repo today. The checklist forces every hook author to think about which one applies.

## The checklist

For every new `Stop` or `SubagentStop` hook, the author confirms in the PR description:

- [ ] **Read the canonical contract.** Linked verbatim above.
- [ ] **Capture stdin first.** The harness pipes JSON on stdin. If the hook needs none of the JSON fields, capture-and-discard with `INPUT=$(cat 2>/dev/null) || INPUT=""`. Do NOT `cat > /dev/null` — you lose the ability to parse.
- [ ] **Gate on `stop_hook_active` before any expensive work.** Use the standard snippet (below) and place it BEFORE: subagent spawns, network calls, file writes, JSONL appends, context emissions to stdout, calls into helper libraries.
- [ ] **The gate is BEFORE the EXIT trap that logs the hook outcome.** If you use `trap 'log_hook_event $?' EXIT`, register the trap first so the short-circuit still gets logged. (See `hooks/auto-pr.sh` for the canonical ordering.)
- [ ] **Add a unit test that pipes `{"stop_hook_active": true}` and asserts exit 0 with no side effects** (no file written, no stdout printed, no JSONL appended). Pattern in `hooks/tests/test-hooks.sh` and `hooks/tests/test-auto-learn-gate.sh`.
- [ ] **Document in the hook header** what side effect would be duplicated if the guard were missing — one comment line, e.g. `# Skips on stop_hook_active to prevent duplicate trajectory rows in nested calls.`
- [ ] **If the hook can return `{"decision": "block"}`** — the gate is non-negotiable and the test MUST also assert that a `stop_hook_active=true` input never produces `decision: block`. A blocking hook without the gate is an infinite-loop bug shipped to prod.
- [ ] **If the hook spawns a subagent or invokes `claude`** — same as above. The gate is non-negotiable.

## The standard snippet

Place AFTER `set -uo pipefail` and AFTER `trap 'log_hook_event $?' EXIT`, BEFORE any other work:

```bash
INPUT=$(cat 2>/dev/null) || INPUT=""
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0
```

If your hook is line-budgeted (e.g. `hooks/worktree-cwd-check.sh` is capped at 50 lines), the two-line collapsed form is acceptable:

```bash
INPUT=$(cat 2>/dev/null) || INPUT=""
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0
```

The trailing `|| echo "false"` / fallback is load-bearing: when the input is empty (some test harnesses run with `< /dev/null`), `jq` exits non-zero and `STOP_HOOK_ACTIVE` would otherwise be unset. With `set -u` active, that crashes the hook. The fallback resolves to `"false"` and the gate is a no-op — exactly what we want for empty stdin.

## When the exemption applies

A hook MAY skip the guard ONLY when ALL of the following hold:

1. It does not return `{"decision": "block"}` under any input.
2. It does not spawn subagents, invoke `claude`, or call any tool that could refire Stop / SubagentStop.
3. It performs zero observable side effects (no stdout to Claude's context, no file writes, no JSONL appends, no metric emission).
4. The author can name a concrete reason adding the guard is harmful.

In practice (4) is almost never true. **Default position: add the guard.** The cost is three lines and the upside is that the hook is safe to extend later without re-deriving the loop analysis.

## Test pattern

Bats:

```bash
@test "hook short-circuits on stop_hook_active=true" {
  out_file="$BATS_TEST_TMPDIR/out"
  echo '{"stop_hook_active": true}' \
    | bash "$REPO_ROOT/hooks/your-new-hook.sh" > "$out_file"
  [ "$status" -eq 0 ]
  [ ! -s "$out_file" ]                       # no stdout
  [ ! -f "$EXPECTED_SIDE_EFFECT_FILE" ]      # no JSONL written
}
```

Plain shell test (matches the existing pattern in `hooks/tests/test-auto-learn-gate.sh`):

```bash
echo '{"stop_hook_active": true}' | bash "$HOOKS_DIR/your-new-hook.sh" > /tmp/out
[ ! -s /tmp/out ] || { echo "FAIL: hook emitted output on stop_hook_active=true"; exit 1; }
```

## Audit log

State of every Stop / SubagentStop hook in this repo as of 2026-05-05 (after the audit landed):

| Hook | Event | Has guard? | Risk class |
|------|-------|-----------|-----------|
| `auto-pr.sh` | Stop | yes | duplicate context message |
| `cost-tracker.sh` | Stop | yes | duplicate cost record |
| `auto-learn-gate.sh` | Stop | yes | duplicate `/learn` trigger banner |
| `subagent-validation.sh` | SubagentStop | yes | duplicate context message |
| `subagent-stop-trajectory.sh` | SubagentStop | yes | duplicate trajectory row + double cleanup of runtime-guard start file |
| `worktree-cwd-check.sh` | SubagentStop | yes | duplicate `main-branch-violations.jsonl` row |
| `cost-feed.sh` | SubagentStop | yes | duplicate cost record |
| `quality-gate-stop.sh` | SubagentStop | yes | duplicate quality-gate forensic |
| `tdd-guard-stop.sh` | SubagentStop | yes | duplicate tdd-guard forensic |

External entries skipped from this audit because they are not maintained in this repo: `$HOME/.local/bin/hcom poll` (Stop), `$HOME/.local/bin/hcom subagent-stop` (SubagentStop), and the `type: agent` Stop registration (a subagent type, not a shell script).
