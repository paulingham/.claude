# Authoring a Hook

Adding a new hook is a GATED path — it requires maintainer review because hooks
enforce CI and security gates. Hooks need DUAL registration (both `hooks/hooks.json`
AND `settings.json`) to fire reliably. Use the scaffolding script:

```bash
bash scripts/new-hook.sh my-guard PostToolUse
```

## Hook Events

| Event | Fires when |
|---|---|
| `PreToolUse` | Before any tool call (can block with exit 2) |
| `PostToolUse` | After any tool call (advisory only) |
| `PostCompact` | After context compaction |
| `Stop` | When the agent finishes |

## Dual Registration (WHY it matters)

Every hook must appear in BOTH:

- `hooks/hooks.json` — loaded when Claude Code runs from the install directory
- `settings.json` — loaded when running from any other working directory

The registration idiom (copy exactly):

```json
{
  "type": "command",
  "command": "bash",
  "args": [
    "-lc",
    "h=\"${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/your-hook.sh\"; [ -x \"$h\" ] && exec \"$h\" || exit 0"
  ],
  "timeout": 10000
}
```

`scripts/new-hook.sh` writes this idiom into both files, validates JSON after writing,
and re-runs the 12-AC registration invariant to confirm.

## Session ID from Stdin

`CLAUDE_SESSION_ID` is **unset** in hook env — always derive it from the JSON payload:

```bash
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
```

## 12-AC Registration Invariant

After wiring, run the invariant to confirm all hooks are registered or allowlisted:

```bash
bash hooks/tests/test-hook-registration-invariant.sh
```

Must output `12 passed, 0 failed`.

## Before Opening a PR

```bash
bash tests/shell/run.sh
pytest -k "readme or verdict or catalog or inventory or stop_hook or counts_match or agent_table or registration"
```
