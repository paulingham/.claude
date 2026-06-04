---
id: instinct-harness-path-cascade
confidence: 0.35
domain: hooks
scope: project
roles: [software-engineer, code-reviewer, architect]
source: best-of-n-selection
created: 2026-06-04T00:00:00Z
evidence_count: 1
last_seen: 2026-06-04T11:27:30Z
---

## Pattern

Any hook or script that writes runtime state (telemetry, JSONL, escape-hatch files) MUST use the full three-tier path cascade when resolving the data directory:

```bash
${HARNESS_DATA:-${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}}
```

Truncating to two tiers (e.g., `${HARNESS_DATA:-$HOME/.claude}`) is a latent production bug: tests pass because they set `HARNESS_DATA` explicitly, but users without `HARNESS_DATA` set and with `CLAUDE_PLUGIN_DATA` configured write to `~/.claude` instead of their configured data dir.

## Why

Best-of-N selection for guard-hardening-telemetry-fixes (2026-06-04): opus-47 candidate used `${HARNESS_DATA:-$HOME/.claude}` in its escape-hatch write paths. All tests passed because the test harness exports `HARNESS_DATA`. The truncated cascade was the decisive correctness factor — sonnet-46 won on this single point. The truncated form would silently misdirect writes for any operator running without `HARNESS_DATA` but with `CLAUDE_PLUGIN_DATA` set (the common deployed configuration).

## How to Apply

- **Build**: whenever writing a file path that should land in the harness data dir, paste the full three-tier cascade — do not abbreviate
- **Code-review**: flag any `${HARNESS_DATA:-$HOME/.claude}` occurrence in hook files; require the full cascade
- **Test hygiene note**: tests that export `HARNESS_DATA` will pass with the truncated cascade — absence of test failure is NOT evidence the cascade is correct; read the expansion manually
- Cross-reference: `hooks/_lib/harness-paths.sh` is the canonical resolution source; align any ad-hoc paths with it
