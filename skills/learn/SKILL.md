---
name: "learn"
description: "Use when user wants to Analyze recent session observations and extract instincts (learned patterns). Reads observations.jsonl, identifies recurring patterns, creates or updates instinct files with confidence scoring. Invoke periodically or at session end."
argument-hint: "Optional: project path or 'global'"
---

# Learn

## What This Skill Does

Analyzes accumulated tool-use observations, pipeline analytics, and review findings to extract "instincts" — atomic learned patterns with confidence scoring. Instincts modify agent behavior in future pipelines, creating a compounding improvement loop.

The key insight: hooks observe 100% of tool usage (deterministic). Pipeline analytics capture every phase outcome. Review findings reveal preventable issues. Patterns emerge from consistent behavior across sessions.

## When to Invoke

- **Automatically** via `/pipeline` Step 7c (Reflect) after every pipeline completion
- Periodically (e.g., every 5-10 sessions, or weekly)
- Manually when you want to review what's been learned

## Process

### 1. Identify Project & Bootstrap Instincts Dir

Resolve the project hash and ensure the per-project instincts directory exists. `mkdir -p` is idempotent — this must succeed on first `/learn` invocation in a project (when no instincts have been created yet) without erroring.

```bash
source "$HOME/.claude/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Idempotent: safe to run on first invocation (no instincts yet) and on repeat runs.
mkdir -p "$HOME/.claude/learning/$PROJECT_HASH/instincts"
```

On first run in a project, this directory will be empty. `/learn` must still succeed — step 5 will populate it from the accumulated observations.

### 2. Read Data Sources

Three data sources feed pattern detection:

#### 2a. Enriched Observations
```bash
cat ~/.claude/learning/{project-hash}/observations.jsonl
```
Note: the `archive/` subdirectory is excluded — `/learn` scans current data only.
Parse the last 500 entries or 7 days. Each record contains:
`{timestamp, session_id, tool, file, project, project_hash, phase, agent_role, outcome}`

#### 2b. Pipeline Analytics
```bash
cat ~/.claude/metrics/pipelines.jsonl | jq 'select(.project == "{project-name}")'
```
Last N pipeline records for this project. Each contains: phase verdicts, review rounds, agent counts, complexity budget.

#### 2c. Review Findings (Current Pipeline Only)
If invoked from pipeline Reflect step, read the review phase state file:
```bash
cat ~/.claude/pipeline-state/{task-id}/review.md  # legacy: ~/.claude/pipeline-state/{task-id}-review.md
```
Extract findings with their severity and category.

### 3. Pattern Detection

Analyze across all three data sources:

| Pattern Type | Signal | Data Source | Example Instinct |
|---|---|---|---|
| **Rework hotspots** | Same files appear in review findings across 3+ pipelines | Pipeline analytics + review state | "Auth module: always validate token expiry before storage" |
| **Phase bottlenecks** | One phase consistently >40% of total review rounds | Pipeline analytics | "Review is the bottleneck — pre-address SOLID violations in build" |
| **Review patterns** | Same finding category in >30% of reviews | Pipeline analytics + review state | "This project: always check for missing error boundaries in React" |
| **Tool preference** | Same tool used >80% for a file type within a phase | Observations | "During build: always Read types.ts before editing services" |
| **File access clusters** | Same files consistently accessed together in same session | Observations (session_id grouping) | "Routes and middleware are always modified together" |
| **Error-prone areas** | Files with outcome=error appearing >3x | Observations | "Config parsing is fragile — add defensive checks" |
| **Phase-specific patterns** | Consistent behavior within a specific pipeline phase | Observations (phase field) | "During review: always check test coverage on new files" |
| **Model efficiency** | Phase outcomes identical across model tiers | Pipeline analytics | "Sonnet handles DB migration reviews as well as Opus" |
| **Test gaps** | Bug fixes correlate with specific file patterns | Pipeline analytics + observations | "Files matching **/hooks/*.ts have 3x the bug rate" |

### 4. Classify Review Findings (Backward Feedback)

For each review finding from the current pipeline, classify:

| Classification | Criteria | Action |
|---|---|---|
| **Preventable by build** | Standard pattern violation (missing validation, SOLID, naming) | Create instinct tagged `role: [software-engineer, frontend-engineer]` |
| **Review-level only** | Architectural concern, cross-cutting issue, subtle bug | No build instinct — this is the reviewer's value-add |
| **Recurring preventable** | Same preventable finding in 3+ pipelines | Promote instinct confidence by +0.2 (urgent pattern) |

Preventable findings become build-targeted instincts: "In {project}, always {check/do X} during build because {review consistently catches Y}."

### 5. Create or Update Instincts

Project-scoped instincts live in `~/.claude/learning/{project-hash}/instincts/`. Global (promoted) instincts live in `~/.claude/learning/instincts/global/`. Check both when looking for existing matches, but create new project-scoped instincts in the per-project directory.

**If instinct exists** (matching pattern, either location):
- Bump `evidence_count`
- Update `last_seen` timestamp
- Adjust confidence: `+0.1` per new evidence, max `0.95`
- Recurring preventable findings: `+0.2` instead of `+0.1`

**If new pattern**, create `~/.claude/learning/{project-hash}/instincts/instinct-{hash}.md`:

```markdown
---
id: instinct-{hash}
confidence: 0.3
category: {discovery|warning|pattern|fragility|decision}  # provenance enum on this instinct file. Distinct from `instinct_categories:` on agent files (which holds role-name tokens for filtering).
domain: {testing|code-style|architecture|workflow|performance|security}
scope: project
project: {project-hash}
roles: [software-engineer, code-reviewer]
applies_to_roles: [software-engineer, code-reviewer]
source: {observation|pipeline-analytics|review-feedback}
created: {ISO 8601}
evidence_count: 1
last_seen: {ISO 8601}
---

## Pattern
{One-sentence actionable description: "Always X when Y because Z"}

## Evidence
- {date}: {observation/finding that triggered this instinct}
```

**Instinct fields** (load-bearing for the loader at `hooks/_lib/instinct_loader.py`):
- `id` (REQUIRED, string): stable identifier; used as the dedup key by the resolver — when the same `id` appears in both project and global directories, the higher-confidence entry wins; on tie, project beats global. Also the secondary sort key (ASC) for stable output ordering.
- `confidence` (REQUIRED, float 0.0-1.0): used both for the floor filter (default `0.4` via `CLAUDE_INSTINCT_MIN_CONFIDENCE`) and the primary sort key (DESC).
- `roles` (REQUIRED, non-empty YAML list of role-name tokens): which agent roles this instinct applies to. Filtered by set-intersection with the spawning agent's `instinct_categories:` (see `agents/{role}.md` frontmatter). **MUST be a YAML list**, not a comma-separated string — `pipeline_frontmatter.parse_frontmatter` would silently corrupt list values to strings, so the loader uses `yaml.safe_load` and `tests/test_learn_roles_enforcement.py` locks the list-not-string contract. **An instinct emitted with empty `roles: []` is invisible to every spawn** (the role-filter intersection is always empty); `/learn` MUST default empty `roles` to `[software-engineer, code-reviewer]` and emit a `source: "learn-warning"` JSONL record (see Step 9 below).
- `category` (RECOMMENDED, enum `discovery|warning|pattern|fragility|decision`): mirrors the scratchpad finding categories, allowing scratchpad → instinct promotion (see `rules/autonomous-intelligence.md` § Scratchpad → Instinct Promotion) to preserve provenance. Optional for backward compatibility with the 4 historical instincts that pre-date this field; the loader does not require it.
- `applies_to_roles` (OPTIONAL, YAML list): forward-looking alias for `roles:`. When present, ignored by the current loader; `roles:` is still the load-bearing field. Future loader versions may merge the two.
- `domain`: appended to each rendered bullet — `- [{confidence:.2f}] {summary} ({domain})`. Optional; defaults to empty string in the renderer.
- `scope`: set by the loader (`"project"` or `"global"`) based on the file's directory. Should not be hand-authored; if present, it is overwritten on load.
- `source`: provenance — `observation` = tool usage patterns; `pipeline-analytics` = phase-level metrics; `review-feedback` = backward feedback from reviewer findings.

**Body extraction contract** (`hooks/_lib/instinct_loader_helpers.py`): the actionable summary rendered into each bullet is the **first non-empty line** of the `## Pattern` body, truncated at 200 chars. The body-extraction regex is `r"^## Pattern[ \t]*\n(.*?)(?=\n##|\Z)"` — note `[ \t]*` (horizontal whitespace only) NOT `\s*` after the heading; `\s` would consume newlines and leak the next section's heading text into the summary when the body is empty. A blank line between `## Pattern` and the body is fine; the extractor strips it. Files missing the `## Pattern` heading or with an all-whitespace body are skipped with a `source: "load-warning"` record.

**Worked example** (canonical emission, single instinct file the loader accepts and the resolver renders correctly):

```markdown
---
id: instinct-validate-input-at-boundary
confidence: 0.85
category: pattern
domain: security
scope: project
project: a1b2c3d4
roles: [software-engineer, code-reviewer, frontend-engineer]
applies_to_roles: [software-engineer, code-reviewer, frontend-engineer]
source: review-feedback
created: 2026-04-15T12:00:00Z
evidence_count: 7
last_seen: 2026-04-25T09:30:00Z
---

## Pattern
Always validate input at the controller boundary, never inside the service layer — the service should assume valid input.

## Evidence
- 2026-04-15: review caught missing validation in PaymentsController
- 2026-04-22: same issue in OrdersController#create
```

This file renders (for a `software-engineer` spawn) as: `- [0.85] Always validate input at the controller boundary, never inside the service layer — the service should assume valid input. (security)`.

#### Roles coverage check (mandatory pre-emission gate)

Before writing the file, validate `roles:`:

1. If the planned `roles:` list is empty → set it to the safe default `[software-engineer, code-reviewer]` AND emit a JSONL warning to `metrics/{session-id}/instinct-injections.jsonl`:

   ```bash
   bash hooks/_lib/log-injection.sh \
     '{"tool_input":{"subagent_type":""}}' \
     '{"file":"<path>","reason":"empty-roles-defaulted","defaulted_to":["software-engineer","code-reviewer"]}' \
     learn-warning instinct-injections.jsonl
   ```

2. If the planned `roles:` list contains tokens not present in any agent's `instinct_categories:` (snapshot lives in `tests/test_agent_instinct_categories.py`) → emit a `learn-warning` record naming the unmatched tokens. Do not refuse to write the file — the unmatched token may target a future agent role.

This gate is enforced by `tests/test_learn_roles_enforcement.py` — the test asserts that every agent file declares `instinct_categories:` as a non-empty YAML list, and that the dedicated loader returns a list for every shipped role. Doc-only enforcement is insufficient; the test locks the contract.

### 6. Prune Stale Instincts

- Instincts not seen in 30+ days: reduce confidence by 0.1 per week of absence
- Instincts at confidence <= 0.0: delete
- Report pruned instincts

### 7. Promote to Global

Instincts meeting ALL criteria:
- Confidence >= 0.8
- Seen in 2+ different projects (different `project` values in observations/analytics)
- Evidence count >= 5

Promote by:
1. Copy to `~/.claude/learning/instincts/global/` subdirectory
2. Set `scope: global` and `project: global`
3. Global instincts are injected into ALL agent prompts regardless of project

### 8. Identify System Improvements (Continuous Self-Improvement)

Beyond instincts, analyze the data for system-level improvement proposals:

| Signal | Proposal |
|---|---|
| A hook fires frequently but never blocks (>50 no-ops) | "Consider moving {hook} to lazy evaluation" |
| Review rounds consistently > 1 for a project | "Build agents need stronger pre-review checklist for {project}" |
| Same phase fails across projects | "Skill {X} may need updating — fails in {N}% of pipelines" |
| Pipeline cycle time trending up | "Investigate bottleneck: {phase} taking {N}% longer than baseline" |

System proposals are surfaced to the user during the Reflect report, not auto-applied.

### 9. Report

```
Learning Report:
- Observations analyzed: N (from {date} to {date})
- Pipeline analytics reviewed: N pipelines
- Review findings classified: N (M preventable, K review-level)

Instinct Changes:
- New instincts created: N
  - [0.30] {pattern description} (source: {source}, roles: {roles})
- Instincts updated: N (confidence changes)
  - [0.50 → 0.60] {pattern description}
- Instincts pruned: N
- Instincts promoted to global: N

Top instincts by confidence:
  [0.85] Always validate input at controller boundary (domain: security, roles: [software-engineer])
  [0.72] Read types.ts before editing services (domain: workflow, roles: [software-engineer])
  [0.50] Check for N+1 queries in ActiveRecord scopes (domain: performance, roles: [software-engineer, code-reviewer])

System Proposals: (if any)
  - {proposal description}
```

### 10. Update Auto-Learn State

Reset the gate counters so `auto-learn-gate.sh` does not re-fire immediately. Run this even when the verdict is `NO_NEW_PATTERNS` or `NO_OBSERVATIONS` — the `/learn` invocation itself satisfies the gate.

Preserve `last_observation_offset` and `last_fired_pipeline_id` (do NOT reset) — the offset tracks file position independent of gate firing; `last_fired_pipeline_id` maintains idempotency against re-firing for the same pipeline.

```bash
source "$HOME/.claude/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
STATE="$HOME/.claude/learning/$PROJECT_HASH/.learn-state.json"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Preserve offset + last_fired_pipeline_id; reset counters + timestamp.
if [[ -s "$STATE" ]]; then
  OFF=$(jq -r '.last_observation_offset // 0' "$STATE")
  FP=$(jq -r '.last_fired_pipeline_id // ""' "$STATE")
else
  OFF=0; FP=""
fi

jq -n --arg ts "$NOW" --argjson off "$OFF" --arg fp "$FP" \
  '{last_learn_run:$ts,pipelines_since_learn:0,observations_since_learn:0,last_fired_pipeline_id:(if $fp=="" then null else $fp end),last_observation_offset:$off}' \
  > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
```

## Phase Output

```
Verdict: LEARNED / NO_NEW_PATTERNS / NO_OBSERVATIONS
Next: Continue with normal work
Artifacts: [list of instinct files created/updated/pruned]
System proposals: [list, if any]
```
$ARGUMENTS
