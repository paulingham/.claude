---
name: "debt-ledger"
description: "Advisory grep-collector that harvests every `DEBT:` deliberate-simplification marker across the tree, renders a ledger grouped by file, and flags `no-trigger` entries (debt with no upgrade-trigger = silent rot). Advisory only, never a gate."
verdict: "DEBT_LEDGER_CLEAN"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional path/glob to scope the sweep (defaults to the whole tree)"
---

# Debt Ledger

> Advisory collector for `DEBT:` markers. Mirrors `/harness:smell-scan`: it surfaces signal, it never blocks. Deliberate debt is a feature — the ledger just keeps it visible and tracks the `no-trigger` count down over time.

## When to Invoke

User-invocable. Not wired into any pipeline phase — run it on demand to take stock of accumulating deliberate-simplification debt.

- **Trigger 1**: Taking stock of where the codebase has parked deliberate simplifications.
- **Trigger 2**: At Reflect, to track whether the `no-trigger` (silent-rot) count is shrinking.
- **Do NOT use when**: You want a gate. This skill is advisory and **never blocks** — it has no failure verdict.

## Inputs

- **Filesystem**: the working tree, readable by the agent.
- **Optional scope**: a path or glob to narrow the sweep; defaults to the whole tree.
- **No prior phase verdict required**: this is a standalone utility collector.

## What It Does

Greps the tree for the `DEBT:` comment marker and renders an advisory ledger.

### Grep pattern

```bash
grep -rn -E '(#|//)[[:space:]]*DEBT:' .
```

No `^` anchor — this intentionally catches **trailing** markers too (e.g. `cache = {}  # DEBT: inline, upgrade when prefixes>3`), not only full-line comments. The comment-smell hook only processes full-line comments; the ledger is broader on purpose.

### Exclusion directories (skip these)

Strip matches whose path is under any of:

- `node_modules/` — vendored JS deps
- `.git/` — VCS internals
- `dist/` — build output
- `build/` — build output
- `target/` — Rust/JVM build output
- `.claude/worktrees/` — ephemeral pipeline worktrees

## Rot Detection

The `DEBT:` grammar is `DEBT: <ceiling>, <upgrade-trigger>` (see `protocols/engineering-invariants.md` § Comments). The second clause (after the comma) is the upgrade-trigger — the condition that should prompt revisiting the debt.

An entry whose body has **no second clause** (no comma, therefore no upgrade-trigger) is flagged **`no-trigger`**: it is silent rot — debt with no exit condition that accumulates invisibly. Every harvested marker is classified as either carrying a trigger or `no-trigger`.

## Procedure

### Step 1: Grep the tree

Run the § What It Does grep, scoped by the optional argument, then strip the § Exclusion directories.

### Step 2: Classify each marker

For each hit, split the body on the first comma. Two or more clauses → ceiling + trigger. One clause only → flag `no-trigger`.

### Step 3: Render the ledger

Group by file per § Output. If zero markers survive after exclusion → emit `DEBT_LEDGER_CLEAN`.

### Step 4: Emit verdict

```
Verdict: DEBT_LEDGER_WRITTEN
```

or

```
Verdict: DEBT_LEDGER_CLEAN
```

## Output

A ledger grouped by file. Per entry, show `file:line`, the ceiling, and the upgrade-trigger — or the `no-trigger` flag when the trigger is absent.

```markdown
## Debt Ledger

Markers found: N   (no-trigger: K)

### path/to/file.rb

| line | ceiling | upgrade-trigger |
|------|---------|-----------------|
| 42 | inline cache keyed by prefix | upgrade to an LRU when prefixes > 3 |
| 88 | hard-coded retry of 3 | `no-trigger` ⚠ silent rot |
```

If zero markers in scope:

```
Debt Ledger: No DEBT markers found (0 in scope).
```

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `DEBT_LEDGER_WRITTEN` | ≥1 `DEBT:` marker found; ledger rendered with ceiling/trigger per entry and the `no-trigger` count. | Advisory / info; never blocks. Reader decides whether to pay down debt. Pipeline continues. |
| `DEBT_LEDGER_CLEAN` | Zero `DEBT:` markers in scope after exclusions ("No DEBT markers found"). | Advisory / info; non-blocking. Pipeline continues. |

The skill MUST emit exactly one verdict per invocation. Both are advisory — there is no failure verdict because deliberate debt is never an error.

## Recommended Cadence

Run periodically or at Reflect to track accumulating debt and shrink the `no-trigger` count over time. The healthy trend is total debt roughly stable and `no-trigger` trending toward zero (every parked simplification carries its own exit condition).

## Anti-Patterns

- **Do NOT hard-block on `no-trigger`**: silent rot is worth surfacing, not gating. Deliberate debt is a legitimate engineering choice; the ledger makes it visible, it does not forbid it. Never a gate.
- **Do NOT anchor the grep with `^`**: trailing markers (`code  # DEBT: ...`) are real debt and must be harvested.
- **Do NOT scan excluded dirs**: `node_modules/`, `.git/`, `dist/`, `build/`, `target/`, and `.claude/worktrees/` are noise — markers there are vendored or ephemeral.

## Tests

Skill-contract + wire-in tests live in `tests/test_debt_ledger_skill.py`:

- SKILL.md exists, frontmatter parses, `phase: utility`, `dispatch: skill-tool`.
- Both verdicts `DEBT_LEDGER_WRITTEN` + `DEBT_LEDGER_CLEAN` named; advisory / never-blocks framing.
- `no-trigger` rot concept and the exclusion directories present; empty-tree → `DEBT_LEDGER_CLEAN`.
- Both verdict-catalog rows (info polarity, `debt-ledger` emitter, `utility` phase); skill-directory row; README skill count.
