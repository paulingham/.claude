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

- **Automatically** via `/harness:pipeline` Step 7c (Reflect) after every pipeline completion
- Periodically (e.g., every 5-10 sessions, or weekly)
- Manually when you want to review what's been learned

## Process

### 1. Identify Project & Bootstrap Instincts Dir

Resolve the project hash and ensure the per-project instincts directory exists. `mkdir -p` is idempotent — this must succeed on first `/harness:learn` invocation in a project (when no instincts have been created yet) without erroring.

```bash
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Idempotent: safe to run on first invocation (no instincts yet) and on repeat runs.
mkdir -p "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/instincts"
```

On first run in a project, this directory will be empty. `/harness:learn` must still succeed — step 5 will populate it from the accumulated observations.

#### 1b. Stamp `last_learn_started` (in-flight sentinel)

BEFORE any expensive work in steps 2+. This sentinel is the in-flight signal the pre-flight queue mechanism (`orchestrator/pipeline-orchestration.md` § Learn-Status Pre-flight Check) reads to detect overlap and defer the next pipeline's `/harness:learn` invocation. Pair with the Step 10 completion stamp (`last_learn_run`).

```bash
STATE="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/.learn-state.json"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$STATE" "$NOW" <<'PY'
import os, sys
sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
import learn_status
learn_status.mark_started(sys.argv[1], sys.argv[2])
PY
```

Predicate (consumed by pre-flight): in-flight ⇔ `last_learn_started > last_learn_run` OR `last_learn_run is null`. Step 10 completes the pair by stamping `last_learn_run` (it MUST also preserve `last_learn_started` so forensics can reconstruct the cycle).

### 2. Read Data Sources

Three data sources feed pattern detection:

#### 2a. Enriched Observations
```bash
cat ~/.claude/learning/{project-hash}/observations.jsonl
```
Note: the `archive/` subdirectory is excluded — `/harness:learn` scans current data only.
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
cat ~/.claude/$state_dir/{task-id}/review.md  # legacy: ~/.claude/$state_dir/{task-id}-review.md
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

#### 3d. Anti-Pattern Mining (rework signals)

Mine "what NOT to do" instincts from rework signals. Per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule, fix-engineer is dispatched on every CHANGES_REQUESTED **and** every PATCH_REJECTED, so the gate is the OR clause `phases.review.rounds >= 2 OR phases.patch_critic.rounds >= 2` — either branch alone proves "fix-engineer ran on this pipeline". False positives are worse than misses; legacy observations missing BOTH fields are SKIPPED, never coerced to 0.

The mining algorithm clusters flat-string `scratchpad_findings` by `sha1(category + ":" + summary_normalised)[:8]` and emits one anti-pattern instinct file per cluster recurring across at least three distinct pipelines. Domain is derived from the parsed category prefix via the lookup `{"warning":"workflow", "fragility":"architecture", "discovery":"workflow", "decision":"architecture", "pattern":"workflow"}` (default `"workflow"`). Confidence formula: `min(0.85, floor + 0.05 * (N - 3))` where `N` is the distinct pipeline count and `floor` is resolved from the domain-weighted map `{workflow: 0.5, testing: 0.6, code-style: 0.6, architecture: 0.7, security: 0.7}` (default `0.5` for unknown domains). Cap is uniform at 0.85; higher-floor domains reach it sooner (architecture/security at N=6, testing/code-style at N=8, workflow at N=10).

**Persona-categorical role tagging** (Slice B). When contributing observations carry `phases.patch_critic.persona_rejections` entries whose `persona` field maps to a recognised role token, the emitted instinct's `roles:` is set to the persona-categorical token(s) **REPLACING** the default `[software-engineer, frontend-engineer]` (M3 — persona path REPLACES, never unions with, defaults). Canonical mapping (single-sourced as `_PERSONA_TO_ROLE` in `hooks/_lib/learn_persona_roles.py`): `correctness` → `patch-critic-correctness`; `regression-risk` → `patch-critic-regression`; `scope-creep` → `patch-critic-scope`. Multi-persona union rendered alphabetically (M5 — diff stability). Mixed-path rule: if ANY contributing pipeline carries a recognised persona, persona-only roles emit; else default roles. Unknown personas (not in the mapping) and malformed entries are silently skipped from the role-tagging path; clusters whose gate cleared ONLY via patch-critic AND whose every persona entry was malformed/unknown are dropped (no derivable role tag). When the gate clears via `phases.patch_critic.rounds >= 2` but the observation has no `persona_rejections` field at all (patch-critic ran but produced no per-persona signal), the cluster emits with default roles `[software-engineer, frontend-engineer]` — distinct from the dropped case where the field is present but every entry is malformed/unknown.

```bash
python3 - "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/observations.jsonl" \
         "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/instincts" <<'PY'
import os, sys
sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
from learn_anti_pattern_mining import mine_anti_patterns
from pathlib import Path
written = mine_anti_patterns(observations_path=Path(sys.argv[1]),
                             instincts_dir=Path(sys.argv[2]))
for p in written:
    print(f"[anti-pattern] emitted {p.name}")
PY
```

Emitted files carry `category: anti-pattern` in the YAML frontmatter; the renderer prefixes their bullets with `AVOID: ` when injected into agent prompts. The `+0.1` floor boost (see `protocols/autonomous-intelligence.md` § Instinct Injection) ensures anti-pattern signals do not crowd out positive guidance — weak positives evaporate when an anti-pattern fires, while the anti-patterns themselves are immune to the boost they trigger (they ship at confidence >= 0.5 by construction).

#### 3e. Sandbox-Verify Fragility Mining

Mine recurring `SANDBOX_FAILED` divergences as `fragility` instincts. The producer is `learn_sandbox_fragility_mining.mine_sandbox_fragility`, the consumer-facing wrapper around the same `is_present`-filtered scan used by `/harness:forensics`. Confidence 0.5 (matches the scratchpad → instinct promotion rule); roles `[software-engineer, sandbox-verify-engineer]`; domain `testing`; category `fragility`.

```bash
python3 - "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/observations.jsonl" \
         "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/instincts" <<'PY'
import os, sys
sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
from learn_sandbox_fragility_mining import mine_sandbox_fragility
from pathlib import Path
written = mine_sandbox_fragility(observations_path=Path(sys.argv[1]),
                                 instincts_dir=Path(sys.argv[2]))
for p in written:
    print(f"[sandbox-fragility] emitted {p.name}")
PY
```

Round-1-only transient divergences are filtered by the existing absence-tolerance contract — only records carrying `phases.sandbox_verify.verdict == "SANDBOX_FAILED"` contribute, so a pipeline that recovered via fix-engineer + Round-2 retry contributes its Round-2 verdict only (the final state, last-writer-wins per Step 5b semantics).

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
category: {discovery|warning|pattern|fragility|decision|anti-pattern}  # provenance enum on this instinct file. Distinct from `instinct_categories:` on agent files (which holds role-name tokens for filtering). The `anti-pattern` value is mined exclusively from rework signals by Step 3d (see above); never set it by hand on a positive-guidance instinct.
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
- `roles` (REQUIRED, non-empty YAML list of role-name tokens): which agent roles this instinct applies to. Filtered by set-intersection with the spawning agent's `instinct_categories:` (see `agents/{role}.md` frontmatter). **MUST be a YAML list**, not a comma-separated string — `pipeline_frontmatter.parse_frontmatter` would silently corrupt list values to strings, so the loader uses `yaml.safe_load` and `tests/test_learn_roles_enforcement.py` locks the list-not-string contract. **An instinct emitted with empty `roles: []` is invisible to every spawn** (the role-filter intersection is always empty); `/harness:learn` MUST default empty `roles` to `[software-engineer, code-reviewer]` and emit a `source: "learn-warning"` JSONL record (see Step 9 below).
- `category` (RECOMMENDED, enum `discovery|warning|pattern|fragility|decision|anti-pattern`): mirrors the scratchpad finding categories, allowing scratchpad → instinct promotion (see `protocols/autonomous-intelligence.md` § Scratchpad → Instinct Promotion) to preserve provenance. Optional for backward compatibility with the 4 historical instincts that pre-date this field; the loader does not require it. The `anti-pattern` value is mined ONLY by Step 3d from `phases.review.rounds >= 2` rework signals — it is never written by hand on a positive-guidance instinct. The loader's `validate()` gates `category` against this six-value enum and returns `"invalid-category"` for unknown values.
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

### 7b. Promote Recurring Scratch Tools to Permanent Skills (Live-SWE Loop)

Beyond instincts, scan observations for the `TOOL_SYNTHESISED_PROMOTABLE` verdict (emitted by `/harness:tool-synthesis` when the agent flagged a scratch tool's signature as reusable across pipelines). When the same tool **signature** (name + one-line description) appears across **≥ 3 distinct pipelines** for this project, scaffold a permanent skill for human review — never auto-merge.

#### Detection

```bash
# Filter pipeline observations for the promotable verdict and group by tool name.
jq -r '
  select(.record_type == "pipeline" and .scratchpad_findings != null) |
  .scratchpad_findings[] |
  capture("(?<verdict>TOOL_SYNTHESISED_PROMOTABLE).*tool=(?<tool>[a-z0-9-]+)") |
  .tool
' ~/.claude/learning/$PROJECT_HASH/observations.jsonl 2>/dev/null \
  | sort | uniq -c | awk '$1 >= 3 { print $2 }'
```

The exact JSON shape is project-dependent — the principle is: count distinct pipeline IDs per `(tool_name, project_hash)` pair from the `TOOL_SYNTHESISED_PROMOTABLE` verdict; promotion gate is **3 distinct pipelines** (not 3 invocations within one pipeline). One-shot tools are invisible to this scan because they emit `TOOL_SYNTHESISED` (no `_PROMOTABLE` suffix).

**Anti-pattern instincts are excluded from the auto-scaffold scan — promotable verdicts only.** Anti-pattern files emitted by Step 3d carry `category: anti-pattern` in their YAML frontmatter and never produce a `TOOL_SYNTHESISED_PROMOTABLE` verdict; they MUST not trigger skill scaffolding regardless of how often they recur. The scratch-tool promotion loop and the anti-pattern instinct loop are independent — neither feeds the other.

#### Scaffold

For each tool name passing the gate that does NOT already have `~/.claude/skills/<tool-name>/SKILL.md`:

```bash
TOOL=<tool-name>
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/skills/$TOOL"
if [[ ! -d "$SKILL_DIR" ]]; then
  mkdir -p "$SKILL_DIR"
  cp "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/skills/_template/SKILL.md" "$SKILL_DIR/SKILL.md"
  # Pre-fill name; reviewer fills the rest.
  sed -i.bak "s/__SKILL_NAME__/$TOOL/g" "$SKILL_DIR/SKILL.md" && rm "$SKILL_DIR/SKILL.md.bak"
fi
```

The scaffolded skill is **not** added to `protocols/verdict-catalog.md` automatically — that requires a human-authored verdict + audit pass. The scaffold is a starting point; the reviewer either:

1. **Promote** — fill in the skill body, add a verdict, run `/harness:harness-audit`, ship as a PR.
2. **Reject** — `rm -rf` the scaffold; the originating tool stays scratch.

#### Surface for review

In the `/harness:learn` Report (Step 9 below), include a section listing every scaffolded skill awaiting human review:

```
Permanent Skill Scaffolds (Live-SWE promotion — awaiting review):
  - skills/<tool-name>/SKILL.md (3 pipelines: PIPE-001, PIPE-014, PIPE-027)
```

Never modify `protocols/verdict-catalog.md`, never wire the new skill into a pipeline phase, never enable it as a slash command. The scaffold is a draft; the human is the gate.

Source for the recurrence threshold: same as scratchpad → instinct promotion (3+ pipelines), aligning with `protocols/autonomous-intelligence.md` § Scratchpad → Instinct Promotion. Inspired by Live-SWE-agent (arXiv 2511.13646).

### 7c. Correlate Cost with Quality Outcomes

Per-pipeline observations carry a `cost_estimate_usd` field (number, USD float — see `protocols/autonomous-intelligence.md` § Observation Capture). This step joins that cost with quality signals from the same record so high-cost-low-quality `(role, task-class)` pairs surface as escalation candidates.

**Input** (single source): `~/.claude/learning/{project-hash}/observations.jsonl`, filtered to `record_type == "pipeline"`. Records missing `cost_estimate_usd` are excluded from the cost aggregates (NOT coerced to `0.0` — absence is "unknown", not "free", per the backward-compatibility note in autonomous-intelligence.md).

**Group key:** `(agent_role, task-class)` — `agent_role` is read from `phases.build.agents[].role` if present, otherwise from `agent_role` on the matching `record_type == "tool_use"` records joined by `session_id`; `task-class` is the `classification` field on the pipeline record (`feature|refactor|bug|batch`).

**Per-group aggregates computed:**

| Aggregate | Computation | Output field |
|---|---|---|
| Total cost | sum of `cost_estimate_usd` across pipelines in the group | `total_cost_usd` |
| Mean cost per pipeline | `total_cost_usd / count(pipelines_with_cost)` | `mean_cost_usd` |
| Mean review rounds | mean of `phases.review.rounds` | `mean_rounds` |
| Rework rate | `count(rework == true) / count(pipelines)` | `rework_rate` |
| Mean mutation kill rate | mean of `phases.verify.mutation_score` when present, else null | `mean_mutation_score` |

**Output:** an in-memory list of group dicts with keys `{agent_role, task_class, pipeline_count, total_cost_usd, mean_cost_usd, mean_rounds, rework_rate, mean_mutation_score}`. The list is fed to existing instinct-extraction logic (Step 5) and to the model-effectiveness recommendation surface (`/harness:eval-model-effectiveness`):

- A `(role, task-class)` pair with `mean_cost_usd` in the top quartile AND (`mean_rounds >= 2.0` OR `rework_rate >= 0.33`) is flagged as a **prefer_opus candidate** — the role is paying premium cost without quality return, so escalating that role to Opus on this task class may improve outcomes. The flag feeds the existing `prefer_opus: true` writer (deferred — see `protocols/autonomous-intelligence.md` § Executor Override (prefer_opus)) when the writer lands; until then, the candidate set is included in the Step 9 report under "Cost-quality candidates".
- A pair with `mean_cost_usd` in the bottom quartile AND `mean_rounds <= 1.0` AND `rework_rate <= 0.10` is flagged as a **downgrade candidate** for `/harness:eval-model-effectiveness` — the role is succeeding cheaply, so Sonnet may suffice. The recommendation report at `~/.claude/learning/{project-hash}/model-recommendations.md` consumes this list (advisory only — no live config change).

Thresholds (`mean_rounds >= 2.0`, `rework_rate >= 0.33`, `mean_rounds <= 1.0`, `rework_rate <= 0.10`) are starting estimates; recalibrate when ≥30 cost-bearing observations exist per project so the quartile bands are statistically meaningful.

**Backward compatibility:** if zero records carry `cost_estimate_usd` (legacy-only data, or pre-producer-wiring window per the implementation-status note), this step emits a single info line in the Step 9 report ("Cost-quality correlation: skipped — no cost-bearing observations") and no candidates are surfaced. The skill MUST NOT raise on absence.

### 7c-bis. Deployment Reliability (project-level)

This step is **project-level, NOT per-group**. Unlike Step 7c which aggregates by `(agent_role, task-class)`, `escape_rate` is computed across ALL pipelines in the project from `deploy_outcome` records, joined by `pipeline_id`. The `deploy_outcome` record type carries no `agent_role` or `task-class` field — it cannot be grouped into the Step 7c per-group table. The `escape_rate` field MUST NOT appear as a key in the Step 7c group-dict output.

**Input:** `learning/{project-hash}/observations.jsonl`, filtered to `record_type == "deploy_outcome"` records.

**Algorithm:**

1. Collect all `deploy_outcome` records. Per `pipeline_id`, keep only the MAX-timestamp record (last-writer-wins: AUTO_ROLLBACK written by deployment-verification supersedes an earlier DEPLOYED written by deploy).
2. Filter the deduplicated records to only those whose `outcome` value is in the four valid enum values `{DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED}`. Records with any other outcome value — including `<unknown>` (written when the producer receives an unrecognised outcome string) — are excluded from BOTH the numerator and the denominator. Optionally surface `n_unparseable = count(records excluded by this filter)` for observability, but `n_unparseable` MUST NOT influence `escape_rate`. `escape_rate = count(outcome ∈ {ROLLED_BACK, AUTO_ROLLBACK}) / count(outcome ∈ {DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED})`. `DEPLOY_FAILED` counts in the denominator but NOT the numerator (deploy attempted, never shipped — no regression escape).
3. Emit `escape_rate`, `n_reverts` (numerator), `n_deploys` (denominator). If `n_unparseable > 0`, also emit it.

**Absence / skip:** if zero `deploy_outcome` records exist, skip this step and render the Step 9 Deployment Reliability line as "not yet measured — no deployed pipelines observed." The skill MUST NOT raise on zero records and MUST NOT coerce absence to `0.0` or `"no escapes"`. This skip applies ONLY to Step 7c-bis and its Step 9 Deployment Reliability line — the Step 7c per-group cost-quality correlation is a separate step on a different record type (`record_type == "pipeline"`) and is NOT skipped or affected by absent `deploy_outcome` records. The two steps are independent.

### 7c-ter. Post-Merge Regression Reliability (project-level)

This step is **project-level, NOT per-group**. Unlike Step 7c which aggregates by `(agent_role, task-class)`, `post_merge_escape_rate` is computed across ALL `pipeline` records in the project that carry a truthy `triggered_by_pipeline_id`. The `triggered_by_pipeline_id` field carries no `agent_role` — it cannot be grouped into the Step 7c per-group table. The `post_merge_escape_rate` field MUST NOT appear as a key in the Step 7c group-dict output. This step is independent of BOTH Step 7c-bis (which reads `deploy_outcome` records) AND Step 7c cost-quality correlation (which reads `pipeline` records on a different filter).

**Input:** `learning/{project-hash}/observations.jsonl`, filtered to `record_type == "pipeline"` records.

**Algorithm:**

1. Collect all `record_type == "pipeline"` records. `n_pipelines` = total count (denominator). This includes pipelines that were later abandoned or failed Ship/CI — the denominator is "recorded pipelines", NOT strictly "merged pipelines" (conservatively biased slightly low vs a merged-only denominator).
2. Numerator: count records where `triggered_by_pipeline_id` is **present AND truthy** AND `classification == "bug"`. A `null` or `""` (empty-string) value MUST NOT count — a falsy value is treated identically to an absent key ("no causal link established"). This is the value-pollution safeguard: only explicit, non-empty task-id strings count as attributed.
3. `post_merge_escape_rate = n_triggered / n_pipelines`. Emit `post_merge_escape_rate`, `n_triggered` (numerator), `n_pipelines` (denominator).

**Absence / skip:** if zero records carry a truthy `triggered_by_pipeline_id`, skip this step and render the Step 9 Post-Merge Regression Reliability line as "not yet measured — no post-merge regressions attributed." The skill MUST NOT raise on zero attributed records and MUST NOT coerce the rate to `0.0`. This skip applies ONLY to Step 7c-ter and its Step 9 Post-Merge Regression Reliability line — Step 7c-bis (deploy reliability) and the Step 7c per-group cost-quality correlation are separate steps on different record filters and are NOT affected by absent `triggered_by_pipeline_id` records. The three steps are decoupled and independent.

### 7d. Promote Durable Memories to Repo-Tracked Proposals

Durable lessons accumulate in two solo-local stores — auto-memory `*.md` files and project instincts — but never graduate into repo-tracked controls (tests, guards, doc one-liners). This step scans both stores for promotion candidates, classifies each via a heuristic ladder, and emits one DRAFT intake-classified task prompt per candidate to `pipeline-state/{task-id}/memory-promotion-drafts/`. The drafts are surfaced in the Step 9 Report. Step 7d is a **proposal generator only — never auto-applies changes; the human is the gate.** It never modifies a security/correctness gate directly.

#### Recurrence Gates

**Instinct store:** an instinct is promotion-eligible when EITHER:
- `evidence_count >= 3` (default N = 3, same as §7b scratch-tool gate), OR
- `confidence >= 0.8`

**Memory store:** a memory (auto-memory `*.md`) is promotion-eligible when EITHER:
- Its `name` (kebab-case identifier) appears as a `[[name]]` backlink in **`>= 3` OTHER individual memory files** (default N = 3), OR
- Its frontmatter carries `durable: true` (explicit engineer opt-in — secondary override).

**Backlink-count exclusions (HIGH-2):** the count is inbound `[[name]]` references from OTHER individual memory files only. It EXCLUDES:
1. The `MEMORY.md` index file — MEMORY.md backlinks nearly every memory by construction and would make every memory appear durable, flooding the report with noise.
2. Self-references — a memory citing its own `name` in its own body.

Match the whole kebab-case `[[exact-name]]` token, not a substring, to avoid name-collision miscounts.

#### Suppression Keys (checked BEFORE the recurrence gate)

A memory or instinct is **skipped entirely** (no draft emitted) when its frontmatter carries either of these keys:

- `promoted: "<PR#>"` — the human shipped the promotion PR and manually wrote this marker after merging. Step 7d does NOT auto-detect merged PRs; the marker is a documented manual operator step (see Draft Emission Contract below). Once set, the item never re-surfaces.
- `dismiss_promotion: true` — the engineer chose not to promote the item. This is the natural inverse of `durable: true`; it silences the proposal without deleting the memory.

Both suppression keys stop all future emission. Step 7d does NOT emit a draft for any memory or instinct carrying `promoted:` or `dismiss_promotion: true`.

#### Classification Ladder

Each promotion-eligible item is classified by a heuristic on the memory's `metadata.type` + body keywords (for memories) or instinct `category` (for instincts):

| Signal | Proposed target |
|---|---|
| Body contains `trap`, `fail-open`, `blind spot`, `false-green`, `bypass`; OR instinct `category: fragility` / `anti-pattern` | A **failing test** or **PreToolUse guard** proposal |
| `type: operational` + body contains `always`, `must`, `never`, `before every`; OR instinct `category: pattern` / `decision` | A **hook** or **SKILL.md checklist-line** proposal |
| `type: feedback` / `architectural` + body contains `actually`, `not advisory`, `is ENFORCED`, `premise false`; OR instinct `category: discovery` / `warning` | A **protocol-doc one-liner** proposal (factual correction) |

Default bucket when no keyword matches: protocol-doc one-liner (lowest blast radius). The heuristic is a starting estimate — the human re-classifies at `/harness:intake`; a mis-bucket costs nothing.

#### Draft Emission Contract

For each promotion-eligible, non-suppressed item, Step 7d writes one file to `pipeline-state/{task-id}/memory-promotion-drafts/<source-name>.md` containing a ready-to-paste `/harness:intake` prompt. The draft body MUST be ordered:

1. **The source memory's `description` field, verbatim** (the one-liner) — so the draft leads with the description and is scannable at a glance without opening the source file. Description-first ordering is mandatory; bucket and recurrence evidence come after.
2. The source memory/instinct identifier and store.
3. The proposed bucket and target type (from the ladder).
4. The recurrence evidence (backlink count or `evidence_count`).
5. The instruction: "Re-run this prompt through `/harness:intake` so it inherits its own tier and reviewer gates."
6. **The operator step (loop-closure):** "After you ship the resulting PR, manually add `promoted: \"#<PR>\"` to this memory's frontmatter so it stops re-surfacing. If you decide NOT to promote it, add `dismiss_promotion: true` instead."

The draft is NEVER auto-executed. Step 7d NEVER emits a draft that modifies a security/correctness gate directly — it proposes a *new* test/guard, leaving any existing-gate change for the human to author.

#### Promoted-Marker Write Contract (manual operator step)

After a human ships a promotion PR, the human **manually** writes `promoted: "#<PR>"` under the `metadata:` section of the source memory file (`~/.claude/projects/{project-hash}/memory/<name>.md`) or the source instinct file (`learning/{project-hash}/instincts/`). Both locations are excluded from the orchestrator code ban (`reflection-protocol.md` § 4: "memory is excluded from orchestrator code ban"), so if the human asks the harness to write the marker, no delegation is required. The canonical path is the human editing the frontmatter directly. Step 7d does NOT auto-detect merged PRs — it only reads the `promoted:` key to decide whether to skip.

#### Absence / Skip

If zero memories and zero instincts clear the recurrence gate (or all eligible items carry suppression keys), Step 7d skips and renders the Step 9 Memory Promotion line as "no durable memories promotable this cycle." The skill MUST NOT raise on an empty memory dir, a memory with no frontmatter, or a malformed `backlinks`/`durable`/`promoted`/`dismiss_promotion` value — treat malformed as not-durable (fail toward not-promoting, the safe direction for a proposal generator). This skip is independent of Steps 7c-bis and 7c-ter.

Never modify `protocols/verdict-catalog.md`, never wire a promoted control directly into a pipeline phase. The draft is a suggestion; the human is the gate.

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

Memory Promotion Proposals (durable-memory promotion — awaiting human approval):
  - {memory-name} ({N} backlinks) → proposed: {target-type}
  - {instinct-id} (evidence_count: {N}) → proposed: {target-type}
  -- or, when no durable items clear the gate --
  no durable memories promotable this cycle.

Deployment Reliability (deploy-phase rollbacks):
  Revert/escape rate: {escape_rate} ({n_reverts} of {n_deploys} deployed pipelines)
  -- or, when no deploy_outcome records exist --
  Revert/escape rate: not yet measured — no deployed pipelines observed.

Post-Merge Regression Reliability (merged work that later triggered a fix pipeline):
  Post-merge regression-escape rate: {post_merge_escape_rate} ({n_triggered} of {n_pipelines} recorded pipelines)
  -- or, when no triggered_by_pipeline_id records exist --
  Post-merge regression-escape rate: not yet measured — no post-merge regressions attributed.

System Proposals: (if any)
  - {proposal description}
```

### 10. Update Auto-Learn State

Reset the gate counters so `auto-learn-gate.sh` does not re-fire immediately. Run this even when the verdict is `NO_NEW_PATTERNS` or `NO_OBSERVATIONS` — the `/harness:learn` invocation itself satisfies the gate.

Preserve `last_observation_offset`, `last_fired_pipeline_id`, AND `last_learn_started` (do NOT reset) — the offset tracks file position independent of gate firing; `last_fired_pipeline_id` maintains idempotency against re-firing for the same pipeline; `last_learn_started` is the symmetric companion stamped by Step 1b and is used by forensics to reconstruct the in-flight window for any given run.

```bash
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
STATE="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/learning/$PROJECT_HASH/.learn-state.json"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Preserve offset + last_fired_pipeline_id + last_learn_started; reset counters + timestamp.
if [[ -s "$STATE" ]]; then
  OFF=$(jq -r '.last_observation_offset // 0' "$STATE")
  FP=$(jq -r '.last_fired_pipeline_id // ""' "$STATE")
  LS=$(jq -r '.last_learn_started // ""' "$STATE")
else
  OFF=0; FP=""; LS=""
fi

jq -n --arg ts "$NOW" --argjson off "$OFF" --arg fp "$FP" --arg ls "$LS" \
  '{last_learn_run:$ts,last_learn_started:(if $ls=="" then null else $ls end),pipelines_since_learn:0,observations_since_learn:0,last_fired_pipeline_id:(if $fp=="" then null else $fp end),last_observation_offset:$off}' \
  > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
```

After this step, `last_learn_run >= last_learn_started` (the predicate flips to "idle"), unblocking the next pipeline's pre-flight queue check.

## Phase Output

```
Verdict: LEARNED / NO_NEW_PATTERNS / NO_OBSERVATIONS
Next: Continue with normal work
Artifacts: [list of instinct files created/updated/pruned]
System proposals: [list, if any]
```
$ARGUMENTS
