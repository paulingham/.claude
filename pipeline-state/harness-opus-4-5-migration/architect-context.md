---
mode: code-archaeology
task_id: harness-opus-4-5-migration
generated: 2026-05-15T00:00:00Z
---

# Code Archaeology Recon — harness-opus-4-5-migration

## Code Archaeology

### Scope summary
- **42 files** reference `opus-4-7` / `claude-opus-4-7` (108 occurrences total).
- **0 files** reference `opus-4-6` / `claude-opus-4-6` outside intake — the prior 4.6→4.7 migration was complete (no historical residue to preserve in code; only the postmortem prose in `CLAUDE.md:47` survives).
- **0 files** reference `effort-2025-11-24` (beta header) — slice 2 is greenfield for the wire format.
- **2 files** already implement `cache_control` infrastructure (slice 3 partially exists — must not duplicate).

### Findings table — opus-4-7 occurrences

Format: `path | classification | lines | unique_token`

**Active config — agent frontmatter `model:` / `executor:` / `advisor:` (MUST migrate)**
- `agents/infrastructure-engineer.md` | active-config | 1 | `executor: claude-opus-4-7` (L14)
- `agents/fix-engineer.md` | active-config | 1 | `executor: claude-opus-4-7` (L14)
- `agents/architect.md` | active-config | 1 | `executor: claude-opus-4-7` (L11)
- `agents/frontend-engineer.md` | active-config | 1 | `advisor: claude-opus-4-7` (L21)
- `agents/software-engineer.md` | active-config | 1 | `advisor: claude-opus-4-7` (L17)
- `agents/security-engineer.md` | active-config | 1 | `advisor: claude-opus-4-7` (L12)
- `agents/code-reviewer.md` | active-config | 2 | `advisor: claude-opus-4-7` (L11, L16 model_conditional)
- `agents/patch-critic.md` | active-config | 1 | `advisor: claude-opus-4-7` (L11)
- `agents/sandbox-verify-engineer.md` | active-config | 1 | `advisor: claude-opus-4-7` (L11)
- `agents/spec-blind-validator.md` | active-config | 1 | `advisor: claude-opus-4-7` (L12)
- `agents/vlm-critic.md` | active-config | 1 | `advisor: claude-opus-4-7` (L9)

**Active config — hooks / resolver / cost (MUST migrate)**
- `hooks/_lib/executor_resolver.py` | active-config | 1 | `return "claude-opus-4-7"` (L12, fallback)
- `hooks/_lib/cost_estimator.py` | active-config | 3 | pricing table keys + rate doc (L8, L14, L36) — pricing table KEY rename
- `hooks/cost-feed.sh` | active-config | 1 | `rate_version:"opus-4-7-2026-04"` (L44) — emitted into costs.jsonl; bump version
- `skills/best-of-n/config.json` | active-config | 1 | `"model_id": "claude-opus-4-7"` (L9)

**Active config — internal-eval baseline paths (MUST migrate; symlinks + fixture filenames)**
- `skills/internal-eval/score/lib/regression-args.sh` | active-config | 1 | `latest-opus-4-7.md` default path (L9)
- `skills/internal-eval/score/stamp-pr-body.sh` | active-config | 2 | `MODEL="opus-4-7"` default + path (L3, L10)
- `skills/internal-eval/tests/_lib/baseline_checks.sh` | active-config | 6 | fixture filenames + symlink assertions
- `skills/internal-eval/tests/_lib/stamp_checks.sh` | active-config | 11 | fixture YAML + filenames + symlink ops

**Documentation prose (MUST migrate)**
- `CLAUDE.md` | doc-prose | 2 | L13 "Default Opus model: claude-opus-4-7"; L15 "80% claim … latest-opus-4-7.md"
- `README.md` | doc-prose | 1 | L553 "80% claim … latest-opus-4-7.md"
- `protocols/advisor-mode.md` | doc-prose | 1 | L7 default pairing prose
- `protocols/autonomous-intelligence.md` | doc-prose | 2 | L263 (long line), L381 `prefer_opus` override → `claude-opus-4-7`
- `orchestrator/agent-orchestration.md` | doc-prose | 2 | L399, L407 resolver examples
- `skills/code-review/SKILL.md` | doc-prose | 1 | L12 pairing
- `skills/security-review/SKILL.md` | doc-prose | 1 | L154 pairing
- `skills/patch-critique/SKILL.md` | doc-prose | 1 | L18 pairing
- `scripts/probe-schema-flips.sh` | doc-prose | 1 | (verify)

**Historical postmortem note (MUST NOT migrate — preserve as historical record)**
- `CLAUDE.md` L43-49 "### Thinking Defaults (Opus 4.7)" + **"Postmortem note (May 2026)"** referencing the 4.7 adaptive-thinking floor change and PR #124. The section header AND the postmortem paragraph are historical context — DO NOT rename "Opus 4.7" → "Opus 4.5" inside the postmortem text; only update active prose around it.
- `CLAUDE.md` L51 "### Advisor-Mode Reviews (Opus 4.7)" header — borderline; treat header as active prose (rename) but inline prose discussing 4.7 mechanism stays historical.
- `protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` | postmortem-historical | 2 | dated proposal in `_proposals/` — DO NOT migrate (L60, L82 baseline references are historical evidence).
- `session-memory/8efffd88329f34786e1828737702e911/notes.md` | postmortem-historical | 3 | session-memory drift notes (L77, L169, L321) — leave as-is (per-session record).

**Test fixtures (MUST migrate — they assert active behavior)**
- `tests/test_advisor_resolver.py` | active-config (test) | 18
- `tests/test_cost_estimator.py` | active-config (test) | 14
- `tests/test_executor_resolution.py` | active-config (test) | 2
- `tests/test_agent_executor_frontmatter.py` | active-config (test) | 2
- `tests/test_pbt_engineer_frontmatter.py` | active-config (test) | 1
- `tests/test_fix_engineer_routing.py` | active-config (test) | 1
- `tests/test_patch_critic.py` | active-config (test) | 1
- `tests/test_spec_blind_validator.py` | active-config (test) | 1
- `tests/shell/test_cost_feed.bats` | active-config (test) | 3
- `tests/shell/test_cost_feed_cache_emit.bats` | active-config (test) | 3
- `hooks/tests/test-eval-model-effectiveness.sh` | active-config (test) | 5

**Pipeline-state (ignore — already 4.5-scoped)**
- `pipeline-state/harness-opus-4-5-migration/intake.md` | other | 2 (intake context only)

### Slice 2 (`effort` param) — existing implementation surface

- `hooks/pre-agent-thinking.sh` — Path-B advisory/log-only resolver for `thinking.effort/display`; emits to `metrics/{session}/hook-injections.jsonl`. **Slice 2's `effort` param differs from this**: 4.5 `effort` is an Anthropic API parameter with beta header `effort-2025-11-24`, not the harness-internal thinking field. Architect must clarify: (a) repurpose this hook to inject the API `effort` field, or (b) introduce a parallel hook. Recommend (a) — the resolver logic (critical/budget gate) is reusable.
- Beta header `effort-2025-11-24`: **no occurrences in tree** — fully greenfield for wire format.
- `CLAUDE_EFFORT` env var + `settings.autoMode.effortLevel` consumed by existing resolver — reusable.

### Slice 3 (caching) — existing implementation surface (DO NOT DUPLICATE)

- `hooks/cache-breakpoint-injector.sh` — already exists, Path-B advisory/log-only. Resolves cache_control anchor positions at PreToolUse:Agent layer. Returns `modified_tool_input` for cache_control; enforcement deferred until schema exposure. Slice 3 extends this hook (do not rewrite).
- `protocols/cost-discipline.md` L19 — documents the existing `cache_control` breakpoint resolution and the companion `skills/cache-audit/SKILL.md`. Slice 3 ratio-monitoring already has a home.
- `enablePromptCaching` — **0 occurrences** in tree; greenfield for Agent SDK flag. Architect must locate Agent SDK consumer (likely orchestrator dispatch surface).

### Prior migration commits (git log)

Searched recent commits for 4.6→4.7 transition patterns:
- `a476a22` — "refactor(agents,hooks): model demotion pass (planning-agent + recon → Haiku, code-reviewer model_conditional, observation-length-cap hook)" — most recent model-rebinding precedent. Demonstrates: (a) cross-agent frontmatter sweep, (b) `model_conditional` pattern in `code-reviewer.md`, (c) hooks library co-changed.
- No direct `opus-4-6 → opus-4-7` commit visible in last 10 commits — migration is older than visible window. The completed-migration evidence is the **absence of `opus-4-6` references** anywhere in the tree (verified via grep, 0 hits).

### Convention / pattern style observations

- **Model strings use dashed form**: `claude-opus-4-7` everywhere (never `claude-opus-4.7`). Slice 1 target: `claude-opus-4-5`.
- **Frontmatter pairing pattern**: review/critic agents use `executor: claude-sonnet-4-6` + `advisor: claude-opus-4-7`. Slice 1 preserves Sonnet executor unchanged; only `advisor:` field migrates.
- **`model_conditional` in `agents/code-reviewer.md` L13-22** — sole agent using this pattern; resolved by `hooks/_lib/advisor_resolver.py::resolve_model_conditional`. Slice 1 must update both arms.
- **Internal-eval fixture pattern**: baseline filenames embed the model token (`2026-04-24-opus-4-7.md`, `latest-opus-4-7.md`). Slice 1 includes both file renames AND symlink updates AND fixture YAML edits (`model: opus-4-7` → `model: opus-4-5`).
- **`rate_version` token in `hooks/cost-feed.sh` L44** — version string is dated (`opus-4-7-2026-04`); slice 1 must mint new version (e.g. `opus-4-5-2026-05`) to keep cost-record provenance intact.

### Fragile areas

1. **`hooks/_lib/cost_estimator.py`** — pricing table (L36) is the single source of truth for cost forecasting. Wrong key here corrupts every cost record downstream. 14 references in `tests/test_cost_estimator.py`.
2. **`skills/internal-eval/tests/_lib/{stamp,baseline}_checks.sh`** — 17 references across two files driving fixture symlinks + filename assertions. High coupling; one missed token breaks the eval harness.
3. **`hooks/_lib/executor_resolver.py` L12** — fallback default; if this is wrong the whole resolver returns a non-existent model. 2 test references.

### Anti-Findings (searched, found nothing — flag for greenfield design)

- `effort-2025-11-24` beta header — 0 occurrences. Slice 2 wire format is greenfield.
- `enablePromptCaching` Agent SDK flag — 0 occurrences. Slice 3 SDK-consumer surface must be located fresh.
- `opus-4-6` / `claude-opus-4-6` — 0 occurrences. Prior migration was clean; no template to copy from in-tree.

## Recommended Architect Read Order

1. `/Users/Paul.Ingham/.claude/CLAUDE.md` (L13-15 active, L43-51 historical-postmortem boundary)
2. `/Users/Paul.Ingham/.claude/hooks/_lib/cost_estimator.py` (pricing table — slice 1 critical surface)
3. `/Users/Paul.Ingham/.claude/hooks/_lib/executor_resolver.py` (fallback default)
4. `/Users/Paul.Ingham/.claude/hooks/cache-breakpoint-injector.sh` (slice 3 — already exists; extend not rewrite)
5. `/Users/Paul.Ingham/.claude/hooks/pre-agent-thinking.sh` (slice 2 — reuse resolver logic for API `effort` param)
6. `/Users/Paul.Ingham/.claude/agents/code-reviewer.md` (sole `model_conditional` pattern — slice 1 dual-arm)
7. `/Users/Paul.Ingham/.claude/skills/internal-eval/tests/_lib/stamp_checks.sh` (highest-density fixture coupling)
8. `/Users/Paul.Ingham/.claude/protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` (preserve unchanged — historical evidence)

---

## Domain Analysis

(Appended by mode=domain-analysis recon, 2026-05-15. Maps each AC to a concrete file:line integration point.)

### Slice 1: `opus-4-7` grep boundary + audit surface

#### Finding D1.1: Postmortem boundary criteria
- **What**: Postmortem-class content has 3 detectable signatures usable as a grep allowlist.
- **Where**: (a) any path under `protocols/_proposals/`; (b) any path under `pipeline-state/*/build-evidence/`, `session-memory/`, or `agent-memory/`; (c) prose paragraphs inside `CLAUDE.md` introduced by the literal token `Postmortem note (` — sole occurrence at `CLAUDE.md:47`. The Default-Opus banner `CLAUDE.md:13` and 80%-claim `CLAUDE.md:15` are **active prose** that describe live config and MUST be rewritten.
- **Why it matters**: Gives architect an executable allowlist. AC "zero hits outside historical postmortem" measured via `grep` excluding those three path/prose classes.

#### Finding D1.2: Verdict-catalog audit does NOT validate `model:` frontmatter
- **What**: The audit checks only bidirectional verdict↔skill agreement. No model allowlist exists anywhere.
- **Where**: `hooks/_lib/verdict_consistency.py:65-81` (`check()` — iterates verdicts only). Grep for `model:` / `claude-opus|sonnet|haiku` in `skills/harness-audit/SKILL.md` returns zero hits.
- **Why it matters**: AC is effectively a tautology — audit passes regardless of model string. Architect should treat as no-op verification OR explicitly add a model-allowlist check as a separate AC.

### Slice 2: effort param + hook-injections.jsonl + beta header

#### Finding D2.1: `pre-agent-thinking.sh` ALREADY emits to `hook-injections.jsonl`
- **What**: Wired end-to-end today; the `effort` field is already present (nested under `resolved.effort`).
- **Where**: `hooks/pre-agent-thinking.sh:24-29` → `hooks/_lib/log-injection.sh:18-23` writes `{timestamp, source, agent_role, resolved: {effort, display, source}}` to `~/.claude/metrics/{session}/hook-injections.jsonl`. Resolver: `hooks/_lib/resolve-thinking.py:34-38` + `hooks/_lib/thinking_resolver.py:35-48`.
- **Why it matters**: Phrase AC as "verify existing emission" rather than "implement emission". Flattening the schema would break observation/cost-report consumers.

#### Finding D2.2: code-reviewer + security-engineer + architect already default ≥ `high`
- **What**: No-op AC.
- **Where**: `hooks/_lib/thinking_role.py:29-32` — `_DOWNGRADE_TO_HIGH` frozenset pins `code-reviewer` and `security-engineer` to `high` floor. `architect` is in no downgrade set → falls through to resolver default `"high"` at `hooks/_lib/thinking_resolver.py:42`. xhigh promotion at `hooks/_lib/thinking_role.py:42-50` (architect: `critical OR budget>=6`).
- **Why it matters**: `high` is the FLOOR. AC phrasing must be "minimum `high`"; do NOT remove xhigh promotion clauses.

#### Finding D2.3: Beta header has NO integration surface in this repo
- **What**: Anthropic API calls happen inside Claude Code runtime, not in this harness.
- **Where**: Greps for `anthropic-ai/claude-agent-sdk`, `from anthropic`, `import anthropic`, `anthropic-beta` across `hooks/`, `agents/`, `skills/`, `orchestrator/` → zero hits. `hooks/_lib/executor_resolver.py` (intake L24) only returns model strings; it does NOT emit headers.
- **Why it matters**: The "beta header `effort-2025-11-24`" AC has no implementation point. Architect MUST escalate to operator: (a) drop AC, (b) reframe as documentation-only, or (c) confirm Claude Code runtime handles it via model string.

### Slice 3: cache_control breakpoint + SDK flag + ≥0.7 read ratio

#### Finding D3.1: Active anchor is `rules-core-tail`, NOT "CLAUDE.md + agent prelude"
- **What**: AC-described anchor position matches a DEFERRED anchor, not the current active one.
- **Where**: `hooks/cache-breakpoint-injector.sh:24-31` invokes resolver; `hooks/_lib/resolve-cache-breakpoints.py:35-48` (`_rules_core_anchor`) computes one advisory anchor `rules-core-tail` (sha256 of `rules/core.md`, ttl `1h`). Three deferred anchors at lines 20-27: `persona-tail` (closest match to AC text), `protocol-tail`, `tool-result-tail`.
- **Why it matters**: Architect must either (a) extend the resolver with a new anchor `claude-md-plus-agent-prelude-tail` matching AC text, or (b) promote the deferred `persona-tail` to that role. Spawn-prompt assembly is Claude Code runtime's job — harness can only annotate via PreToolUse hook.

#### Finding D3.2: Agent SDK flag has no integration surface
- **What**: Same root cause as D2.3 — no SDK consumer in tree.
- **Where**: Zero hits for SDK imports.
- **Why it matters**: `enablePromptCaching: true` AC has no implementation point. Escalate to operator. Cache control in this harness is via PreToolUse hook (D3.1), not an SDK flag.

#### Finding D3.3: Cache-read ratio metric exists; threshold is named constant at 0.60 (below AC target 0.70)
- **What**: Per-spawn `read_ratio` computed and aggregated into a markdown report (not a live dashboard).
- **Where**:
  - Per-spawn emission: `hooks/_lib/cache-jsonl-emit.py:25-40` computes `read_ratio = read / (read + create + input)`, appends to `metrics/{session}/cache.jsonl`. Driver: `hooks/cost-feed.sh:46` on `SubagentStop`.
  - Aggregator + threshold: `skills/cache-audit/SKILL.md:32-40` declares `READ_RATIO_TARGET = 0.60`. Report path: `metrics/reports/{YYYY-MM-DD}-cache.md`. Verdict polarity `info` per `rules/verdict-catalog.md` (CACHE_AUDIT_READY does not gate any phase).
  - Test fixture (lockstep): `tests/test_cache_audit_read_ratio_target_constant.py`.
- **Why it matters**: Raising threshold to ≥0.70 requires TWO edits (skill + test fixture). Architect must also decide whether to flip verdict polarity from `info` to `failure` so the threshold gates anything — today it's purely advisory.

## Anti-Findings (domain-analysis)

- **Anthropic SDK / API header surface** — confirmed absent across `hooks/`, `agents/`, `skills/`, `orchestrator/`.
- **`executor_resolver.py` is not an API integration point** — exists at `hooks/_lib/executor_resolver.py` but only returns model strings.
- **Model allowlist enforcement** — no code path validates `model:` frontmatter against any whitelist.

## Recommended Architect Read Order (domain-analysis additions)

1. `/Users/Paul.Ingham/.claude/hooks/_lib/thinking_role.py` (role effort policy — Slice 2 D2.2, already correct)
2. `/Users/Paul.Ingham/.claude/hooks/_lib/resolve-cache-breakpoints.py` (anchor surface — Slice 3 D3.1)
3. `/Users/Paul.Ingham/.claude/hooks/_lib/verdict_consistency.py` (audit scope — Slice 1 D1.2)
4. `/Users/Paul.Ingham/.claude/skills/cache-audit/SKILL.md` L32-40 (threshold constant — Slice 3 D3.3)
5. `/Users/Paul.Ingham/.claude/hooks/_lib/log-injection.sh` (jsonl schema — Slice 2 D2.1)
