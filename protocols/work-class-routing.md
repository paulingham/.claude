# Work-Class Routing Protocol

How the harness decides **which dispatch shape a task gets**. The goal is to prevent a doc edit from paying feature-sized dispatch cost while preserving full pipeline rigour for real engineering work.

This protocol is read by `/harness:intake` (gear-read step) and `/harness:pipeline` (route step). It is auto-loaded when either skill spawns. Classification itself happens earlier, in the **three-gear classifier** (`hooks/_lib/gear-select.sh`), which runs on `UserPromptSubmit` and persists its verdict to `gear-${sid}` session state before intake or pipeline dispatch begins.

## Why this exists

Without a work-class read, a doc-only sweep and a feature would share the same pipeline shape if their budget+critical happen to match. User phrasing (`critical`, `important`) is trusted directly — there is no classifier cross-check. Result: low-stakes work routes through Plan → heavy challenger team → multi-slice Build → 5-agent Final Gate, burning 12-15 subagent spawns for what amounts to a find/replace.

## Design principle

> **Gear is orthogonal to budget. Auto-classification overrides user phrasing. Every override is logged.**

Three rules govern routing:

1. **Class first, budget second.** Classify the work into one of three gears — **PAIR**, **BUILD**, **PIPELINE** — based on **what the request implies** (keyword/shape evidence in the prompt), not what the user said about stakes. Budget informs *intra-gear* shape (e.g. multi-slice Build), not *which gear*.
2. **Default light, escalate on evidence.** Polarity is inverted from the legacy tier fingerprint: the default gear is **PAIR** (the lightest), escalating to BUILD or PIPELINE only when a detector positively fires. A gate that cannot evaluate its input (empty/malformed prompt) fails to the **heaviest** gear (PIPELINE) — fail SAFE means fail HEAVY, never silently light.
3. **Bidirectional override with forensics.** A one-word NL override (`just pair`, `build it`, `full pipeline`) is resolved by `gear-select.sh` itself before intake ever runs; `[force-pipeline]` is a separate safety-override token read later, at `/harness:intake` Step 1.5. Both log to `metrics/{session}/intake-overrides.jsonl`.

## The three gears

| Gear | Default? | Class | Examples | Dispatch target |
|---|---|---|---|---|
| **PAIR** | Yes (default) | Question / doc / config / mechanical / trivial code | "How does X work?", README edits, settings.json keys, rename sweeps, ≤1-file/≤15-line trivial code | Direct answer, or one of the PAIR sub-behaviours below |
| **BUILD** | No — escalate on evidence | Bug fix / standard feature | Failing test + targeted fix, new AC in an isolated module, "build it", "implement this feature" | One worktree subagent, TDD, code-review, PR |
| **PIPELINE** | No — escalate on evidence | Critical / cross-cutting | Auth, payment, security, multi-repo, schema/migration work, "full pipeline" | Full multi-agent `/harness:pipeline` (Plan → Plan Validation → Build → Security Review → Final Gate → Ship → Deploy → Reflect) |

PAIR is the fast path — it never enters `/harness:pipeline`. BUILD and PIPELINE are today's `/harness:pipeline`, unchanged in substance from the former T4-T6 dispatch shapes.

### PAIR sub-behaviours (dispatch capabilities preserved from the tier model)

PAIR is not one dispatch target — it is the lightest gear, and its own classifier hands off to whichever lightweight capability fits the request shape. These capabilities are unchanged from the retired tier model; only the outer classification vocabulary changed:

| Request shape | PAIR sub-behaviour |
|---|---|
| Question / spike ("How does X work?", "Investigate Y") | Direct answer, or `/harness:tech-spike` for a throwaway prototype |
| Tracked-doc edit (README/CLAUDE.md/protocol updates, comments) | Lightweight worktree subagent (Iron Law 3 — orchestrator never writes source directly; delegates to a worktree subagent) |
| Config-only (settings.json keys, agent frontmatter, hook entry syntax — NOT hook script bodies) | `/harness:harness-config` |
| Mechanical sweep (rename, find/replace, lint-fix, import-sort, dependency bump across ≥3 uniform files) | `/harness:batch-pipeline` |

BUILD and PIPELINE are single dispatch targets — BUILD always means one worktree subagent running Build phase + code-review + Ship; PIPELINE always means the full `/harness:pipeline` phase sequence (with Best-of-N or PDR-RTV Build variants for the heaviest cases, gated by budget+critical exactly as the retired T6 tier was).

## Gear classification (`hooks/_lib/gear-select.sh`)

Classification happens as a `UserPromptSubmit` hook, `hooks/_lib/gear-select.sh`, BEFORE `/harness:intake` or `/harness:pipeline` dispatch ever runs — it persists the verdict to state key `gear-${sid}`. `/harness:intake` Step 1.5 (Gear Read) then reads that persisted value; it does not re-derive it. No fingerprint computation happens inside intake — the gear is already resolved and persisted by the time intake runs.

### Override detection (checked first)

Natural-language override phrases in the prompt force a specific gear regardless of classification evidence, resolved by `_gear_select_has_override` INSIDE `gear-select.sh` before the escalation regex is even evaluated:

| Phrase pattern | Forced gear |
|---|---|
| "just pair" / "pair on this" | PAIR |
| "build it" / "build this properly" | BUILD |
| "ship it properly" / "take it all the way" / "full pipeline" | PIPELINE |

### Evidence-based classification (when no override matches)

Regex-based, `hooks/_lib/gear-select.sh::_gear_select_classify` — no model call, $0:

1. **PIPELINE evidence** — prompt contains any of the **canonical 17-keyword list**: `auth`, `token`, `secret`, `payment`, `crypto`, `password`, `session`, `billing`, `oauth`, `jwt`, `cors`, `csrf`, `cookie`, `admin`, `rbac`, `cert`, `signature` — or `migration`, `schema`, `cross-repo`, `multi-repo`, `critical`. Kept lockstep across `hooks/_lib/gear-select.sh`, `skills/intake/SKILL.md`, and this file.
2. **BUILD evidence** — prompt matches a build/implement/add/create/refactor/migrate verb paired with a feature/endpoint/component/service/caching/layer/dashboard noun, OR names "new endpoint" / "new component" / "new feature", OR references "three/multiple/several files".
3. **Default** — PAIR.

### Fail-safe

An empty or unparseable prompt (or a `gear_select` invocation with no stdin) emits **PIPELINE**, never PAIR — an unevaluable classification input must never silently downshift. There is no tiebreaker call; ambiguous input fails safe to PIPELINE rather than falling through to a paid resolution step.

### Persistence

The resolved gear is written to `gear-${sid}` session state (keyed by session id, not PPID — the classifier and every downstream gear-gated hook run as separate subprocesses with different PPIDs). `/harness:intake` and `/harness:pipeline` read this state; neither recomputes it.

## Dispatch matrix

| Phase | PAIR | BUILD | PIPELINE |
|---|---|---|---|
| Plan (architect) | — | light/full (by scale) | full |
| Plan Validation | — | `/harness:plan-self-validation` or heavy if `budget≥7` | heavy always |
| Build | sub-behaviour dispatch (see gear table above) | single agent or multi-slice | Best-of-N or PDR-RTV |
| Polish | — | if `budget≥7` | yes |
| Code Review | reviewer reads diff only (PAIR-shaped sub-behaviours) | code-reviewer | code-reviewer + adversarial |
| Security Review | only if hooks touched | yes | yes |
| Final Gate | verify (smoke only, PAIR-shaped sub-behaviours) | full 4-agent | full 5-agent (+ spec-blind) |
| Ship (PR) | yes | yes | yes |
| Deploy | — | conditional | yes |
| Reflect | yes (terse, Haiku, 100 tok cap) | yes | yes |

## Override discipline

| Token in user prompt | Effect | Forensic record |
|---|---|---|
| (default) | Auto-classify via `gear-select.sh` | `intake-overrides.jsonl` records classifier verdict |
| `[force-pipeline]` | Force `gear: PIPELINE` regardless of the persisted classifier verdict (read at `/harness:intake` Step 1.5, not inside `gear-select.sh`) | `intake-overrides.jsonl` `direction: upshift` |
| one-word NL override (`just pair`, `build it`, `full pipeline`, ...) | Resolved inside `gear-select.sh` before the escalation regex runs | `intake-overrides.jsonl` records the resolved gear + `phrasing_honoured: true` |
| User phrasing claims "critical" but gear = PAIR | **Gear wins**, `critical: false` set, override logged | `intake-overrides.jsonl` `direction: phrasing-rejected` |

## Plan-phase re-gear sanity check

Gear classification runs on the user prompt at `UserPromptSubmit` (via `gear-select.sh`, before `/harness:intake` or `/harness:pipeline` ever runs). Architect's Plan reveals the actual scope. **Re-check the Plan's affected-files list against the rules/core.md safety-upshift floor** as Step 0 of Plan Validation. If the floor fires, upshift the rest of the pipeline to PIPELINE and emit `ROUTING_UPSHIFTED`. Downshifts at this stage are not honoured — once a pipeline is dispatched at BUILD+, it completes at BUILD+.

Catches the failure mode: user says "tidy up the docs" but architect's plan actually touches 8 source files.

## rules/core.md special handling

`rules/core.md` is load-bearing — every spawn reads it. But not every line in it is equally critical. The principled rule: **the semantic surface matters, not the file**.

| Surface inside `rules/core.md` | Gear floor |
|---|---|
| Iron Laws (numbered 1-8) | **PIPELINE** (Best-of-N + adversarial review mandatory) |
| Code Shape Rules (per-language function limits, CC≤5, nesting≤2 — `protocols/engineering-invariants.md` § Code Shape) | **PIPELINE** |
| Worktree + Commit Protocol section | **BUILD** |
| Pipeline Phase Order text | **BUILD** |
| "Where to Look Next" index (just redirectors) | **PAIR** allowed |

Detection: a second-pass Haiku call (~300 tokens) reads the diff content and looks for Iron-Law-touching tokens (`Iron Law`, `IRON LAW`, `NEVER`, `ATTRIBUTION`). If matched, upshift to PIPELINE. Same pattern applies to `protocols/atdd-procedure.md` (Iron Law 1 source) and `protocols/verdict-catalog.md` (verdict additions = BUILD; verdict removals = PIPELINE).

## Forensic logging schema

Every gear resolution and every override writes a JSONL line to `metrics/{session}/intake-overrides.jsonl`:

```json
{
  "timestamp": "ISO-8601",
  "task_id": "...",
  "gear_emitted": "PAIR|BUILD|PIPELINE",
  "gear_initial": "PAIR|BUILD|PIPELINE",
  "detector_phase": "rules|fallthrough",
  "detector_confidence": "high|medium|low",
  "user_phrasing_signals": ["critical", "important", ...],
  "phrasing_honoured": true|false,
  "override_token": "[force-pipeline]|null",
  "safety_override_fired": true|false,
  "predicted_files": ["path/a.md", "path/b.json"],
  "fingerprint_cost_tokens": 0
}
```

Read by `/harness:forensics` to detect:
- Silent miscategorisation (downshift followed by escalation later in pipeline)
- Override abuse (high `[force-pipeline]` rate from a single source)
- Classifier blind spots (high `fallthrough` rate)

## Quality safety analysis

| Failure mode | Mitigation |
|---|---|
| Auth change classified as config-only | Security-signal keyword match on `auth`, `secrets`, `crypto`, `.env`, `password`, `token`, `session` (and the full 17-keyword list) → forces PIPELINE |
| Feature classified as doc-only because of phrasing | PAIR default only applies absent a feature-verb+feature-noun match or multi-file mention; a single code file signal escalates to BUILD |
| Hook script edit classified as config-only | Gear classification runs on the prompt, not file diffs directly — `gear-select.sh` errs toward BUILD/PIPELINE on ambiguity per its fail-safe polarity |
| Test file edit classified as trivial | `gear-select.sh`'s fail-safe default (PIPELINE on any unevaluable input) plus the plan-phase safety-upshift floor (Step 0 of Plan Validation) catch this downstream even if the prompt-level classifier under-escalates |
| Trivial-code edit hides a security change | The canonical 17-keyword list forces PIPELINE regardless of prompt brevity — `auth\|token\|secret\|payment\|session\|crypto\|password\|billing\|oauth\|jwt\|cors\|csrf\|cookie\|admin\|rbac\|cert\|signature` |
| Plan got skipped for work that needed it | BUILD/PIPELINE plan unchanged — no gear skips Plan. PAIR requires no plan because the change is the spec |
| Gear read hides real complexity | Plan-phase re-gear check catches scope creep; upshifts mid-pipeline |

## Hook implementation

`hooks/intake-fingerprint-audit.sh` (PostToolUse Skill matcher for `/harness:intake`):

- Reads emitted `task_class` from intake output
- Reads override metadata
- Writes one JSONL line per gear resolution
- **Advisory/logging only** — no enforcement, no exit-2
- Respects `CLAUDE_HOOK_PROFILE=minimal` (exits 0 silently)
- After 30 days of clean data (classifier accuracy ≥95%), schedule a follow-up to demote to cron-scheduled audit rather than per-intake

## Interaction with existing protocols

- **Iron Law 5** ("NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.") applies to **BUILD/PIPELINE**. PAIR dispatches outside `/harness:pipeline` and is governed by its own sub-behaviour's verdict catalog entry. This is not an exception to the Iron Law — it is a clarification that the Iron Law's scope is the pipeline, not all work.
- **Iron Law 3** (orchestrator never writes source code; protected-location enforcement via `hooks/_lib/is-protected-path.sh`) governs the PAIR doc-only sub-behaviour. Tracked-doc edits route to a lightweight worktree subagent which commits the change with full audit trail.
- **Complexity Budget** still computes (`/harness:intake` Step 2). It controls *intra-gear* dispatch shape (multi-slice Build at BUILD, Best-of-N vs PDR-RTV at PIPELINE). It no longer controls *which* gear.
- **`critical` flag** still computes but is **gear-filtered**. If gear = PAIR and no safety-override file in scope, `critical: true` from user phrasing is rejected and logged.
- **`bestofn` and `pdr_rtv` flags** only fire at PIPELINE AND budget>=7. BUILD forces both false regardless of critical or budget. `bestofn` also requires `critical==true`; the `[best-of-n]` override token bypasses the gear+budget gate. SSOT: `hooks/_lib/bestofn_gate.py`.

## Where to look next

| Need | File |
|------|------|
| Gear classifier implementation | `hooks/_lib/gear-select.sh` |
| Complexity Budget dimensions | `protocols/operational-protocol.md` |
| Pipeline phases (BUILD/PIPELINE) | `protocols/pipeline-protocol.md` |
| Parallel dispatch (BUILD/PIPELINE fan-out) | `protocols/parallel-dispatch-protocol.md` |
| Verdicts emitted by intake | `protocols/verdict-catalog.md` § fingerprint + routing entries |
| Gear Read (Step 1.5) | `skills/intake/SKILL.md`; `hooks/_lib/intake-fingerprint-emit.py` |
| Hook implementation | `hooks/intake-fingerprint-audit.sh` |
| Orchestrator dispatch on gear | `skills/pipeline/SKILL.md` Step 3 |
| PAIR worktree-subagent dispatch | Iron Law 3 in `rules/core.md`; `hooks/_lib/is-protected-path.sh` |
