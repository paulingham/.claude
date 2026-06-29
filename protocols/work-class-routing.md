# Work-Class Routing Protocol

How `/harness:intake` and `/harness:pipeline` decide **which dispatch shape a task gets** before complexity-budget computation. The goal is to prevent a doc edit from paying feature-sized dispatch cost while preserving full pipeline rigour for real engineering work.

This protocol is read by `/harness:intake` (fingerprint step) and `/harness:pipeline` (route step). It is auto-loaded when either skill spawns.

## Why this exists

Today `/harness:intake` recognises 8 task classifications but emits only `(budget, critical, bestofn, pdr_rtv)` for the dispatcher. A doc-only sweep and a feature share the same pipeline shape if their budget+critical happen to match. User phrasing (`critical`, `important`) is trusted directly — there is no fingerprint cross-check. Result: low-stakes work routes through Plan → heavy challenger team → multi-slice Build → 5-agent Final Gate, burning 12-15 subagent spawns for what amounts to a find/replace.

## Design principle

> **Task class is orthogonal to budget. Auto-detection overrides user phrasing. Every override is logged.**

Three rules govern routing:

1. **Class first, budget second.** Fingerprint the work into one of seven tiers (T0-T6) plus the T3H sub-lane based on **what files change** and **how they change**, not what the user said. Budget informs *intra-tier* shape (e.g. multi-slice Build), not *which tier*.
2. **Downshift requires positive signal.** A pipeline only drops below standard (T4+) if a detector explicitly fires. Absent that, default is the current full-pipeline shape. Safety bias: never under-dispatch.
3. **Bidirectional override with forensics.** `[force-pipeline]` user token forces upshift; `[force-class:Tn]` forces downshift. Both log to `metrics/{session}/intake-overrides.jsonl`.

## The seven tiers

| Tier | Class | Examples | Dispatch target |
|---|---|---|---|
| **T0** | Question / Spike | "How does X work?", "Investigate Y" | Direct answer or `/harness:tech-spike` |
| **T1** | Doc-only | README/CLAUDE.md edits, protocol updates, comments | **Lightweight worktree subagent** (tracked-doc edits) |
| **T2** | Config-only | settings.json keys, agent frontmatter, hook entry syntax (NOT hook script bodies) | **`/harness:harness-config`** |
| **T3** | Mechanical sweep | rename, find/replace, lint-fix, import-sort, dependency bump | **`/harness:batch-pipeline`** |
| **T3H** | Trivial code change | ≤1 code file, ≤15 changed lines, no tests, no security keyword, internal-shape-only | `/harness:pipeline` (trimmed: Build + diff-only code-review + Ship) |
| **T4** | Bug fix | Failing test + targeted fix | `/harness:pipeline` (lightweight) |
| **T5** | Standard feature | New AC, single-slice, isolated module | `/harness:pipeline` (standard) |
| **T6** | Critical / cross-cutting | Auth, payment, security, multi-repo, system-wide | `/harness:pipeline` (heavy: Best-of-N or PDR-RTV) |

T0-T3 are fast paths. T3H is a trimmed continue-tier for trivial code changes. T4-T6 are today's `/harness:pipeline`, unchanged.

## Fingerprint (the auto-detection step)

Inserted into `/harness:intake` as **Step 1.5: Fingerprint**, between Step 1 (classify) and Step 2 (budget). Hybrid model: rule-based first, Haiku tiebreaker on ambiguity.

### Phase 1 — Rule-based pass (no model call, $0)

Regex/glob detectors. Conjunctive AND positive-evidence only.

```yaml
detectors:
  T1_doc_only:
    AND:
      - "ALL predicted file paths match: *.md OR *.txt OR *.rst OR docs/* OR README*"
      - "NO predicted change includes a code-block, config-block, or shell-script body edit"
      - "NO file in scope is referenced by skills/*/SKILL.md as a code dependency"

  T2_config_only:
    AND:
      - "ALL predicted file paths match: settings.json OR *.yml OR *.yaml OR *.toml OR agents/*.md (frontmatter only)"
      - "NO predicted change touches function bodies, control flow, or hook .sh script logic"

  T3_mechanical_sweep:
    AND:
      - "User prompt OR architect plan describes a UNIFORM transformation"
      - "Pattern phrases match any of: 'rename X to Y' | 'replace all' | 'convert to' | 'lint-fix' | 'bump version' | 'import sort'"
      - "Predicted changed files >= 3 AND change shape is identical across files"
      - "NO security-sensitive file in scope"
```

### Phase 2 — Safety override (always runs, never downshifts)

ANY of these force T4+ regardless of detector match:

- Predicted scope includes `hooks/*.sh` body changes (not entry-syntax-only)
- Predicted scope includes `rules/core.md` Iron Law surface (see § rules/core.md special handling)
- Predicted scope includes any test file (Tier 1 tests, ATDD guarantees)
- User prompt contains `auth` | `payment` | `token` | `secret` | `crypto` | `password` | `session` in change-target context
- Predicted scope includes `auth/*`, `secrets/*`, `*crypto*`, `*.env`, or files matching configured security-sensitive paths

### Phase 3 — Haiku tiebreaker (~500 tokens, only on ambiguity)

If Phase 1 detectors all return "no" or "ambiguous", run a single Haiku call:

```
Input: user prompt + first 50 lines of git status + any file paths mentioned
Output: predicted file list (JSON array) + best-guess tier + confidence (low/medium/high)
```

Re-run Phase 1 detectors against the predicted file list. If a tier is confidently identified, emit it. If still ambiguous, **default to T4+** with `confidence: low` logged to forensics.

### Cost in expectation

- 70% rule-confident: $0
- 25% Haiku-resolved: ~$0.0008
- 5% fall-through to T4+: ~$0.0008 (wasted but safe)

Average fingerprint cost: ~$0.0002 per intake. Compared to ~$0.15 wasted on misclassified heavy dispatch, fingerprinting is ~750× cheaper than no fingerprint.

## Dispatch matrix

| Phase | T0 | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|---|
| Plan (architect) | — | — | — | — | light | full | full |
| Plan Validation | — | — | — | — | `/harness:plan-self-validation` | heavy if `budget≥7` | heavy always |
| Build | — | lightweight worktree subagent | `/harness:harness-config` | `/harness:batch-pipeline` parallel | single agent | single or multi-slice | Best-of-N or PDR-RTV |
| Polish | — | — | — | — | — | if `budget≥7` | yes |
| Code Review | — | — | reviewer reads diff only | code-reviewer (diff-only) | code-reviewer | code-reviewer | code-reviewer + adversarial |
| Security Review | — | — | only if hooks touched | only if security-sensitive | yes | yes | yes |
| Final Gate | — | — | verify (smoke only) | verify + patch-critique | full 4-agent | full 4-agent | full 5-agent (+ spec-blind) |
| Ship (PR) | — | yes | yes | yes | yes | yes | yes |
| Deploy | — | — | — | — | conditional | conditional | yes |
| Reflect | yes | yes (terse, Haiku, 100 tok cap) | yes (terse) | yes | yes | yes | yes |

## Override discipline

| Token in user prompt | Effect | Forensic record |
|---|---|---|
| (default) | Auto-detect | `intake-fingerprint.jsonl` records detector verdict |
| `[force-pipeline]` | Force T4+ regardless of fingerprint | `intake-overrides.jsonl` `direction: upshift` |
| `[force-class:Tn]` | Force a specific tier | `intake-overrides.jsonl` `direction: downshift, target: Tn` |
| User phrasing claims "critical" but fingerprint = T1/T2 | **Fingerprint wins**, `critical: false` set, override logged | `intake-overrides.jsonl` `direction: phrasing-rejected` |
| `[force-class:Tn]` with safety-override file in scope | Safety wins, escalate to T4+ | `intake-overrides.jsonl` `direction: safety-block` |

## Plan-phase re-fingerprint sanity check

The fingerprint runs on the user prompt at `/harness:intake`. Architect's Plan reveals the actual scope. **Re-run the fingerprint against the Plan's affected-files list** as Step 0 of Plan Validation. If the new tier is higher than the original, upshift the rest of the pipeline and emit `ROUTING_UPSHIFTED`. Downshifts at this stage are not honoured — once a pipeline is dispatched at T4+, it completes at T4+.

Catches the failure mode: user says "tidy up the docs" but architect's plan actually touches 8 source files.

## rules/core.md special handling

`rules/core.md` is load-bearing — every spawn reads it. But not every line in it is equally critical. The principled rule: **the semantic surface matters, not the file**.

| Surface inside `rules/core.md` | Tier floor |
|---|---|
| Iron Laws (numbered 1-8) | **T6** (Best-of-N + adversarial review mandatory) |
| Code Shape Rules (per-language function limits, CC≤5, nesting≤2 — `protocols/engineering-invariants.md` § Code Shape) | **T6** |
| Worktree + Commit Protocol section | **T5** |
| Pipeline Phase Order text | **T5** |
| "Where to Look Next" index (just redirectors) | **T1** allowed |

Detection: a second-pass Haiku call (~300 tokens) reads the diff content and looks for Iron-Law-touching tokens (`Iron Law`, `IRON LAW`, `NEVER`, `ATTRIBUTION`). If matched, upshift. Same pattern applies to `protocols/atdd-procedure.md` (Iron Law 1 source) and `protocols/verdict-catalog.md` (verdict additions = T4; verdict removals = T6).

## Forensic logging schema

Every fingerprint resolution and every override writes a JSONL line to `metrics/{session}/intake-overrides.jsonl`:

```json
{
  "timestamp": "ISO-8601",
  "task_id": "...",
  "tier_emitted": "T1|T2|T3|T4|T5|T6",
  "tier_initial": "T1|...|T6",
  "detector_phase": "rules|haiku|fallthrough",
  "detector_confidence": "high|medium|low",
  "user_phrasing_signals": ["critical", "important", ...],
  "phrasing_honoured": true|false,
  "override_token": "[force-pipeline]|[force-class:T3]|null",
  "safety_override_fired": true|false,
  "predicted_files": ["path/a.md", "path/b.json"],
  "fingerprint_cost_tokens": 0|~500|~800
}
```

Read by `/harness:forensics` to detect:
- Silent miscategorisation (downshift followed by escalation later in pipeline)
- Override abuse (high `[force-class:T1]` rate from a single source)
- Detector blind spots (high `fallthrough` rate)

## Quality safety analysis

| Failure mode | Mitigation |
|---|---|
| Auth change classified as config-only | Safety override on `auth/*`, `secrets/*`, `*crypto*`, `*.env`, `password`, `token`, `session` keywords → forces T4+ |
| Feature classified as doc-only because of phrasing | T1 detector requires ALL files to match doc patterns; single `.py`/`.ts`/`.rb` in scope kills T1 |
| Hook script edit classified as T2 config | T2 detector excludes hook `.sh` body changes; only entry syntax allowed |
| Tier 1 test edit classified as T3 sweep | Safety override on test files → forces T4+ |
| Mechanical sweep silently broke behaviour | T3 still runs Code Review (diff-only) + Final Gate verify (smoke). Skipped phases are Plan/Plan-Validation/QA/Accept — not behaviour validation |
| Plan got skipped for work that needed it | T4-T6 plan unchanged. T3 inherits plan from the user prompt (which IS the plan for a sweep). T1/T2 require no plan because the change is the spec |
| Fingerprint hides real complexity | Plan-phase re-fingerprint catches scope creep; upshifts mid-pipeline |

## Hook implementation

`hooks/intake-fingerprint-audit.sh` (PostToolUse Skill matcher for `/harness:intake`):

- Reads emitted `task_class` from intake output
- Reads override metadata
- Writes one JSONL line per fingerprint resolution
- **Advisory/logging only** — no enforcement, no exit-2
- Respects `CLAUDE_HOOK_PROFILE=minimal` (exits 0 silently)
- After 30 days of clean data (detector accuracy ≥95%), schedule a follow-up to demote to cron-scheduled audit rather than per-intake

## Interaction with existing protocols

- **Iron Law 5** ("NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.") applies to **T4-T6**. T0-T3 dispatch outside `/harness:pipeline` and are governed by their own skill's verdict catalog entry. This is not an exception to the Iron Law — it is a clarification that the Iron Law's scope is the pipeline, not all work.
- **Iron Law 3** (orchestrator never writes source code; protected-location enforcement via `hooks/_lib/is-protected-path.sh`) governs T1. Tracked-doc edits route to a lightweight worktree subagent which commits the change with full audit trail.
- **Complexity Budget** still computes (`/harness:intake` Step 2). It controls *intra-tier* dispatch shape (multi-slice Build at T5, Best-of-N vs PDR-RTV at T6). It no longer controls *which* tier.
- **`critical` flag** still computes but is **fingerprint-filtered**. If fingerprint = T1/T2 and no safety-override file in scope, `critical: true` from user phrasing is rejected and logged.
- **`bestofn` and `pdr_rtv` flags** only fire at T6 AND budget>=7. T4/T5 force both false regardless of critical or budget. `bestofn` also requires `critical==true`; the `[best-of-n]` override token bypasses the tier+budget gate. SSOT: `hooks/_lib/bestofn_gate.py`.

## Where to look next

| Need | File |
|------|------|
| Complexity Budget dimensions | `protocols/operational-protocol.md` |
| Pipeline phases (T4-T6) | `protocols/pipeline-protocol.md` |
| Parallel dispatch (T5/T6 fan-out) | `protocols/parallel-dispatch-protocol.md` |
| Verdicts emitted by intake | `protocols/verdict-catalog.md` § fingerprint + routing entries |
| Hook implementation | `hooks/intake-fingerprint-audit.sh` |
| Orchestrator dispatch on tier | `skills/pipeline/SKILL.md` Step 3 |
| T1 worktree-subagent dispatch | Iron Law 3 in `rules/core.md`; `hooks/_lib/is-protected-path.sh` |
