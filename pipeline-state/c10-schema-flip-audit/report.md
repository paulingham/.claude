# C10 — Schema-Flip Audit

Probe-and-report of whether the four advisory hooks gating Path-B-→-Path-A
promotion can flip yet. Each hook is waiting on either a new field on the
Agent tool's `tool_input` schema or on harness-side support for a PreToolUse
hook returning `modified_tool_input`. This audit empirically tests the
consumer-side wiring of each hook and aggregates the last 30 days of
forensic JSONL records to count would-fire occurrences.

- Probe driver: `scripts/probe-schema-flips.sh` (committed in this PR).
- Raw probe output: `pipeline-state/c10-schema-flip-audit/probe-output.json`
  (committed in this PR).
- Verdict scope: probe-and-report only. **Zero hook files modified.**

## Probe Results

| Hook | Field | Probe verdict | Last-30d would-fire count |
|------|-------|---------------|---------------------------|
| `hooks/pre-agent-thinking.sh`   | `tool_input.thinking`         | **ABSENT** — resolver consumer-side ready; harness never passes the field | 0 |
| `hooks/pre-agent-advisor.sh`    | `tool_input.advisor`          | **ABSENT** — resolver does NOT inspect the field today (no `explicit` branch) | 0 |
| `hooks/pre-agent-allowlist.sh`  | `tool_input.allowed_tools`    | **ABSENT** — resolver consumer-side ready (`would_block` branch wired); harness never passes the field | 0 |
| `hooks/instinct-injector.sh`    | `modified_tool_input` (PreToolUse output) | **ABSENT** — resolver renders instincts correctly; orchestrator-injected pair record never written → 325 / 0 drift over 30 days | 0 (orchestrator-injected pair count) |

All four LANDED checks come back ABSENT. No promotion PRs are filed in this audit run.

### Probe verdict detail

- **`thinking`** — probe with `tool_input.thinking={effort:"xhigh",display:"text"}` returns `decision=SKIP, source=explicit`; probe without the field returns `decision=LOG, source=role`. The resolver correctly stops emitting forensic records the instant the harness ever passes `thinking`. Across 1,125 last-30d `hook-injections.jsonl` records, **zero** carry `resolved.source=="explicit"` — the harness has never passed the field.
- **`advisor`** — both probes (with and without `tool_input.advisor`) return identical output (`source=no-api-key` in this environment, where `ANTHROPIC_API_KEY` is unset; on a populated environment it would be `frontmatter-pairing` either way). The resolver has no `explicit` branch — `tool_input.advisor` is structurally ignored. Promoting this hook needs the resolver to grow an explicit branch FIRST, then the harness to expose the field. Across 762 last-30d `advisor-dispatch.jsonl` records, zero carry `resolved.source=="explicit"`.
- **`allowed_tools`** — probe with `allowed_tools=["Read","ToolThatDoesNotExist"]` returns `action=would_block, source=superset-requested, offending_tools=["ToolThatDoesNotExist"]`; probe without returns `action=advisory, source=schema-absent`. Resolver is fully wired. Across 639 last-30d `tool-allowlist.jsonl` records, zero carry `action=="would_block"` — the harness has never passed `allowed_tools`.
- **`modified_tool_input`** — instinct-injector resolver renders a non-empty learned-patterns block when matching instincts exist (probe: `count_kept=2, rendered_chars=516`). The 30-day forensic shape is `325 logged-with-kept / 0 orchestrator-injected` records — drift of 325. The Path-B disclosure surface (logged without paired orchestrator-injected) is wide open across the entire 30-day window. Promotion to enforcement requires both (a) harness honouring `modified_tool_input` returned from PreToolUse hooks AND (b) the orchestrator-side caller writing the paired `orchestrator-injected` record on every actual splice. The hook's contract docs in `rules/_detail/autonomous-intelligence.md` § JSONL forensic format already describe both records.

## Still-waiting notes (per ABSENT field)

| Field | One-line status |
|-------|-----------------|
| `tool_input.thinking` | No signal yet in the Agent input schema visible to this orchestrator (`additionalProperties: false`, `thinking` not in `properties`). No matching item in the recent Anthropic Agent SDK changelog. |
| `tool_input.advisor` | No signal yet — and resolver-side `explicit` branch must be authored first regardless of harness support. Current resolver vocabulary: `frontmatter-pairing | env-disabled | no-api-key | no-pairing-frontmatter`. |
| `tool_input.allowed_tools` | No signal yet in the Agent input schema. Resolver and `agent_tools_loader` are enforcement-ready; promotion is a one-line flip in `hooks/pre-agent-allowlist.sh`. |
| `modified_tool_input` (PreToolUse output) | No signal yet in the Claude Code hook protocol changelog for PreToolUse hooks honouring a `modified_tool_input` return shape. Orchestrator-side splice + paired-record writer are the second precondition; both are documented but not yet emitted in any 30-day session. |

## Promotion plans (filed for whenever the field lands)

These are NOT executed in this audit. Each is a single-file flip; if any field flips, a separate PR per hook lets the change be reverted independently.

| Hook | Promotion one-liner |
|------|---------------------|
| `hooks/pre-agent-thinking.sh` | Replace the trailing `exit 0` (line 30) with: emit `modified_tool_input` JSON containing `tool_input` augmented by the resolved `thinking` block when `DECISION == "LOG"`; keep `exit 0`. (Resolver already returns `effort/display/source` in line 26's `RESOLVED`.) |
| `hooks/pre-agent-advisor.sh` | First teach `advisor_resolver.resolve` an `explicit` branch that prefers `tool_input.advisor`/`tool_input.executor` over frontmatter; then make line 35 emit `modified_tool_input` carrying the resolved pairing on `LOG`. Two-step — resolver change ships before hook change. |
| `hooks/pre-agent-allowlist.sh` | Replace the trailing `exit 0` (line 34) with: `[[ "$(printf '%s\n' "$RESOLVED" \| jq -r '.action')" == "would_block" ]] && exit 2 \|\| exit 0`. Resolver returns `would_block` only when `tool_input.allowed_tools` is a strict superset of frontmatter `tools:`. |
| `hooks/instinct-injector.sh` | Replace the trailing `exit 0` (line 28) with: emit `modified_tool_input` JSON containing `tool_input.prompt` prefixed by the rendered `## Learned Patterns` block when `count_kept > 0`. Keep `exit 0`. The orchestrator-side splice in `orchestrator/agent-orchestration.md` § Spawn Procedure must continue writing the paired `source: "orchestrator-injected"` JSONL record so drift stays observable post-promotion. |

## Forensic counts (last 30 days)

Captured by `scripts/probe-schema-flips.sh` on 2026-05-05.

| File | Records inspected | Would-fire count |
|------|-------------------|------------------|
| `hook-injections.jsonl`     | 1,125 | 0 (records with `resolved.source == "explicit"`) |
| `advisor-dispatch.jsonl`    | 762   | 0 (records with `resolved.source == "explicit"`) |
| `tool-allowlist.jsonl`      | 639   | 0 (records with `action == "would_block"`) |
| `instinct-injections.jsonl` | 359 logged + 142 load-warning | 325 logged-with-kept / 0 orchestrator-injected (drift = 325) |

## Verdict

**No promotions executed.** All four awaited fields remain ABSENT. The audit
is the deliverable; every hook's resolver is enforcement-ready (with the
exception of `advisor_resolver`, which still needs a one-time `explicit`
branch added when the field lands).

When any field flips, run the corresponding promotion-plan one-liner as a
separate single-file PR. Re-run `scripts/probe-schema-flips.sh` immediately
before opening the PR to confirm a non-zero would-fire count for that
field.
