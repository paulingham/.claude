---
name: "smell-scan"
description: "Advisory Fowler-catalog smell sweep on changed source files. Detects 9 architectural smells (Feature Envy, Data Clumps, Primitive Obsession, Message Chains, Shotgun Surgery, Divergent Change, Middle Man, Inappropriate Intimacy, Speculative Generality) via Grep/Read heuristics. Produces a ranked P1/P2/P3 candidate table with tag column — advisory only, never a gate."
verdict: "SMELLS_CLEAN"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "List of changed file paths (one per line or space-separated)"
---

# Smell Scan

## When to Invoke

Invoked by the **code-reviewer agent** at the Build code-review step — analogous to how the security-engineer invokes `/harness:skill-security-lint`. Findings flow into the code-reviewer's output as an advisory section, never a separate gate. May also be invoked manually.

- **Diff touches source files**: invoke to sweep changed source files for architectural smells before the SOLID/DRY rubric runs.
- **Do NOT invoke on config or doc changes**: skip invocation when the diff contains only `*.md`, `*.json`, `*.yaml`, `*.toml`, or lock files — filter these out first (see § Input Contract).
- **Advisory only**: never hard-blocks the pipeline. The code-reviewer decides whether a finding warrants a CHANGES_REQUESTED verdict.

## Inputs

- **Changed file list**: one file path per entry; passed by the code-reviewer from the branch diff.
- **Filesystem**: the actual changed files, readable by the agent.
- **No prior phase verdict required**: this is a utility sub-scan called from within the Build code-review step.

## Input Contract

### Source-file scope (INCLUDE)

Apply heuristics only to files with these extensions:

`.ts` `.tsx` `.js` `.jsx` `.py` `.rb` `.go` `.rs` `.java` `.sh`

### Exclusions (EXCLUDE)

Strip from the input list before scanning:

- `*.md` — documentation
- `*.json` — config / data
- `*.yaml` / `*.yml` — config
- `*.toml` — config
- `*.lock` — lockfiles
- Any file whose path includes `spec/`, `test/`, `tests/`, or `__tests__/` — test files

**Empty after filter**: if the post-filter list is empty, emit `SMELLS_CLEAN (0 source files in scope)` immediately — fail-open, never raise.

## Smell Catalog

Nine architectural smells, none owned by shape hooks. Each has a detection heuristic the agent can execute via Grep/Read, a confidence label, and one example.

| # | Smell | Confidence | Detection Heuristic | Example |
|---|-------|------------|--------------------|---------| 
| 1 | **Feature Envy** | high | Method body references another class/module's attributes/methods ≥3× more than its own. Grep for `obj.field` / `other.method()` chains; count cross-boundary refs vs self refs. | `OrderPrinter.print()` calls `order.customer.address.city` — clearly envying `Customer`. |
| 2 | **Data Clumps** | high | Same ≥3 parameters appear together across ≥2 function signatures. Grep parameter lists for repeated combos (e.g. `host, port, user` or `start_date, end_date, timezone`). | `connect(host, port, user)` and `reconnect(host, port, user)` → extract `ConnectionConfig`. |
| 3 | **Primitive Obsession** | medium | Domain concept expressed as a raw `str`/`int`/`dict` at a module boundary. Look for param names like `user_id: str`, `money: float`, `status: str` in public signatures. | `charge(amount: float, currency: str)` → use `Money` value object. |
| 4 | **Message Chains** | high | Law of Demeter violation: `a.b().c().d()` with ≥3 derefs in one expression. Grep for `.` chains of depth ≥3 (`\w+\.\w+\(\)\.\w+\(\)\.\w+`). | `user.profile().address().city()` — hide behind `user.city()`. |
| 5 | **Shotgun Surgery** | judgment-call | One conceptual change requires parallel edits across ≥3 files with NO common import/module ancestor — true cross-cutting scatter. P3 only; verify manually. **Fires ONLY when ≥3 changed files share NO common import/module ancestor.** Normal parameter fan-out across files does NOT qualify. | Renaming a domain constant requires touching `models/`, `api/`, `jobs/`, and `config/` independently. |
| 6 | **Divergent Change** | judgment-call | One file is changed for ≥2 clearly unrelated method-clusters — two distinct concerns living in the same class. P3 only; verify manually. **Requires naming ≥2 unrelated method-clusters** (not just "it's big"). | `UserService` has both payment-processing methods and email-notification methods — separate concerns. |
| 7 | **Middle Man** | medium | A class/module that consists almost entirely of delegation — most methods just forward to another object. Read the file; if >50% of methods are single-line delegations, flag. | `OrderFacade.create(args) → order_service.create(args)` with no added logic. |
| 8 | **Inappropriate Intimacy** | judgment-call | Two classes/modules access each other's internal implementation details (private fields, internal helpers) rather than going through a public API. Report-only; requires manual verification of access patterns. | `PaymentProcessor` directly reads `Order._internal_discount_rules`. |
| 9 | **Speculative Generality** | judgment-call | Abstractions, hooks, or flexibility built for hypothetical future use — YAGNI violations detectable at design surface. P3 by default; P2 only with concrete blast-radius evidence. See § Over-Build / YAGNI Lens for detection sub-tags. | `AbstractBaseProcessor` with one concrete subclass, or a dead `on_before_process` hook with zero callers. |

### Over-Build / YAGNI Lens

Speculative Generality is Fowler's canonical name for YAGNI-over-building. Rather than introducing five separate smell names (which would itself be over-building), this lens uses five detection sub-tags under the single named smell:

| Sub-tag | Meaning | Signal |
|---------|---------|--------|
| `yagni:` | Abstraction with a single implementation or a single caller — generalisation without present need. | Interface/abstract class with exactly one concrete subclass; function with one call site. |
| `delete:` | Unused, speculative, or dead flexibility — hooks, extension points, or configuration knobs with zero callers. | Dead `on_*` hooks, unused strategy variants, unreachable `if feature_flag:` branches. |
| `stdlib:` | Hand-rolled logic that the standard library already provides. | Custom `flatten()`, `memoize()`, or `retry()` that duplicates `itertools`, `functools`, or equivalent. |
| `native:` | Dependency that duplicates a platform or framework feature already available. | Vendoring a UUID library in an environment that ships `uuid` natively. |
| `shrink:` | Same logic achievable in materially fewer lines — measurable delete-to-simplify opportunity. | 30-line pipeline that collapses to 6 lines with a standard combinator. |

**Multi-tag output shape**: when a candidate matches multiple sub-tags, render ONE row per candidate with comma-separated tags in the `tag` column (e.g. `yagni:, delete:`). Do NOT split into one row per tag — that inflates the table.

**Lean already. Ship.**: when no over-build candidates are found under any sub-tag, the clean-case verdict is `SMELLS_CLEAN`. Emit: "Over-build lens: Lean already. Ship."

**Net deletable lines footer**: for each over-build finding include a footer line summarising total deletable lines:

```
net: -42 lines (estimate)
```

The integer is an ESTIMATE — directional, not exact (e.g. `net: -12 lines (estimate)`). It signals the order-of-magnitude simplification opportunity, not a guaranteed LOC reduction.

**Ranking**: P3 by default (judgment-call, like Shotgun Surgery and Divergent Change). P2 only when blast-radius is concrete (e.g. the abstraction is consumed across ≥3 modules). Never P1 — over-build does not have the cross-boundary coupling risk that drives P1.

**Advisory; never a gate**: findings from the over-build lens are advisory only. They inform code-reviewer judgment but never independently block the pipeline.

**Shape-hook non-overlap**: the over-build lens operates at the architectural and design surface only. It does NOT report: long function, deep nesting, long parameter list, or WHAT-comments — those are owned by `function-body-check.sh` and `comment-smell-check.sh`. Reporting them here would duplicate enforcement already covered by shape hooks. See § Anti-Patterns.

## Procedure

### Step 1: Filter inputs

Apply the § Input Contract exclusions. If empty → emit `SMELLS_CLEAN (0 source files in scope)` and stop.

### Step 2: Grep / Read heuristics (per smell)

For each source file in scope, apply the heuristics from the § Smell Catalog. Use Grep for pattern detection, Read for context. Assign P1/P2/P3 per the § Ranking Rules.

### Step 3: Rank and cap

Apply § Ranking Rules and § Output-Volume Policy.

### Step 4: Emit ranked table

Format per § Output Format.

### Step 5: Emit verdict

```
Verdict: SMELLS_FOUND
```

or

```
Verdict: SMELLS_CLEAN
```

## Ranking Rules

Tier assignment uses **blast-radius × confidence**:

- **P1** — high confidence + multi-file / cross-boundary impact. Feature Envy and Message Chains that cross module boundaries, or Data Clumps in public API signatures.
- **P2** — high or medium confidence, single-file structural issue. Blast-radius ≥ 2 required (affects ≥2 call sites or ≥2 module consumers). A single-line clump that has one call site does NOT qualify as P2.
- **P3** — judgment-call smells or boundary-only signals. Shotgun Surgery, Divergent Change, Inappropriate Intimacy, and any smell where the evidence is ambiguous. Always carry "verify manually" caveat.

## Output-Volume Policy

- **Cap: top 5 candidates per tier.** If more than 5 candidates exist in a tier, emit the 5 highest-impact ones only.
- **P3 suppression**: if more than 10 P3 candidates are detected, suppress the entire P3 section and instead emit a single line:

  ```
  N P3 candidates suppressed (noise control); re-run scoped to fewer files to see them.
  ```

- **P2 threshold**: a finding requires blast-radius ≥ 2 to appear in the P2 tier. Single-occurrence clumps are either P3 or omitted.

## Output Format

### Ranked table schema

```
| file:line | smell | tier | why it matters | suggested refactor | tag |
```

Each row:

| file:line | smell | tier | why it matters | suggested refactor | tag |
|-----------|-------|------|----------------|--------------------|----|
| `src/order.py:42` | Feature Envy | P1 | `OrderPrinter` accesses 4 `Customer` fields directly — breaks encapsulation, couples changes | Extract Class / Move Method | — |
| `src/proc.py:10` | Speculative Generality | P3 | `AbstractBaseProcessor` has one subclass — no present need for abstraction | Inline Class | `yagni:` |

The `tag` column is ADDITIVE — all 5 original columns (file:line, smell, tier, why it matters, suggested refactor) are preserved. For non-over-build smells use `—` in the `tag` column. For Speculative Generality findings, list matching sub-tags comma-separated (e.g. `yagni:, delete:`).

Fowler refactor names to use in "suggested refactor": Extract Class, Move Method, Replace Data Value with Object, Introduce Parameter Object, Hide Delegate, Extract Module, Inline Class.

### Over-build net footer

When Speculative Generality findings are present, append a summary footer below the ranked table:

```
net: -12 lines (estimate)
```

Where the integer is the estimated total deletable lines across all over-build candidates. This is directional — the actual reduction may differ (e.g. `net: -42 lines (estimate)`).

If no over-build findings exist: omit the footer entirely.

### Advisory findings block

```markdown
## Smell Scan Findings

Files scanned: N
Source files after filter: M

### P1 — High blast-radius, high confidence

| file:line | smell | tier | why it matters | suggested refactor | tag |
|-----------|-------|------|----------------|--------------------|
| ...       | ...   | P1   | ...            | ...                |

### P2 — Structural issue, medium-to-high confidence

(none / rows)

### P3 — Judgment-call / boundary-only (verify manually)

(none / rows / suppressed)
```

If `SMELLS_CLEAN`:

```
Smell Scan: CLEAN (N files scanned, 0 candidates)
```

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `SMELLS_FOUND` | ≥1 ranked smell candidate detected. | Advisory; code-reviewer folds findings into review output as an advisory section. Never a hard block. Pipeline continues. |
| `SMELLS_CLEAN` | No smell candidates, or 0 source files in scope after filtering. | Advisory; non-blocking. Pipeline continues normally. |

The skill MUST emit exactly one verdict per invocation.

## Anti-Patterns

- **Do NOT hard-block on SMELLS_FOUND**: this is an advisory scan. The code-reviewer decides whether findings constitute a gate failure. Findings alone do not block ship — never a gate.
- **Do NOT re-implement shape-hook-owned smells**: the following are explicitly OUT — owned by shape hooks (`rules/core.md` § Code Shape Rules):
  - Long function / long method — OUT (shape hook owns per-language method-length limits)
  - Long parameter list — OUT (shape hook: ≤4 params rule)
  - Large class / large file — OUT (shape hook: `CLAUDE_FILE_LINE_LIMIT` 300-line cap)
  - Deep nesting — OUT (shape hook: nesting ≤2 rule)
  - Comments (explanatory) — OUT (shape hook: WHAT-comments blocked)
  Naming these here would create noise by duplicating enforcement already covered. The 9-smell catalog is the complete scope.
- **Do NOT emit P1/P2 on judgment-call smells**: Shotgun Surgery, Divergent Change, and Inappropriate Intimacy are always P3. Assigning them P1 or P2 inflates confidence beyond what heuristic evidence supports.
- **Do NOT emit findings on config/doc/test files**: the § Input Contract exclusion list is strict. Scanning `*.md` or `tests/` generates noise with zero actionable signal.
- **Do NOT fabricate findings**: if evidence is ambiguous, omit or classify P3 with "verify manually". A false-positive P1 is worse than a missed smell.

## Tests / Validation

### Heuristic validation requirement (load-bearing)

Before shipping any change to this skill, validate heuristics against ≥5 REAL files from `skills/*/SKILL.md`, `agents/*.md`, and `hooks/_lib/*.py`. The goal: **0 spurious P1/P2 findings** on the harness's own corpus.

Prose-heavy SKILL.md and agent definition files will contain `.` chains (Markdown, not code) and parameter lists (natural language, not function signatures) — the heuristics must not fire on these.

Specific checks:
- Message Chains grep must not fire on Markdown link syntax or prose like "a.b section".
- Data Clumps grep must not fire on prose parameter descriptions.
- Feature Envy must require code context (function body), not trigger on prose mentioning other modules.

### Test coverage

Unit tests live in `tests/test_smell_scan_skill.py` (frontmatter + wire-in assertions AC1–AC17).

Key coverage:
- SKILL.md exists, frontmatter parses with all required keys (AC1).
- `phase: utility`, `dispatch: skill-tool` (AC2).
- Frontmatter `verdict:` is `SMELLS_CLEAN`, body names both `SMELLS_FOUND` and `SMELLS_CLEAN` (AC3).
- Both verdict rows in `protocols/verdict-catalog.md` with `info` polarity and `smell-scan` emitter (AC4).
- `/harness:smell-scan` row in `protocols/skill-directory.md` Active Skills section with both verdicts (AC5).
- README `## Skills (72)` and `# 72 skills` (AC6).
- All 9 smell names present literally in body (AC7).
- Anti-Patterns names and excludes long function, long parameter list, deep nesting as OUT (AC8).
- Advisory/never-blocks framing present (AC9).
- Ranked table schema header with all 5 columns (AC10).
- Top-5-per-tier cap and P3 suppression >10 policy (AC11).
- Shotgun Surgery and Divergent Change marked judgment-call/P3 (AC12).
- Include/exclude extensions and empty-after-filter → `SMELLS_CLEAN` (AC13).
- `code-reviewer` named as canonical invoker in § When to Invoke (AC14).

No state file written — this is a utility sub-scan within the Build code-review step.
